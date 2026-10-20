"""Outcome-independent quota changes and retention of the original SRS prefix."""
import copy
import unittest

from observer.core import GateError, MODES
from observer.snapshot_sample import draw_from_frame
from observer.snapshot_supplement import allocate, extend_draw, verify_extension


class SupplementTests(unittest.TestCase):
    def fixture(self):
        frame=dict(scope='SYNTHETIC_ONLY',frames={m:{m+'big':[str(j*1000+i) for i in range(50)],
                   m+'small':[str(j*1000+100+i) for i in range(5)],m+'zero':[]} for j,m in enumerate(MODES)})
        baseline=draw_from_frame(frame,'ad'*32)
        allocations={m:allocate({b:x['N'] for b,x in vs.items()},{b:x['m'] for b,x in vs.items()},20)
                     for m,vs in baseline['samples'].items()}
        return frame,baseline,allocations

    def test_exact_total_lower_bounds_and_population_caps(self):
        result=allocate(dict(big=1000,medium=100,tiny=1,zero=0),dict(big=10,medium=10,tiny=1,zero=0),111)
        self.assertEqual(result['counts'],dict(big=100,medium=10,tiny=1,zero=0))

    def test_baseline_floors_are_not_added_twice_to_proportional_quota(self):
        result=allocate(dict(big=787,mid=48,small=34,one=1,two=2),dict(big=10,mid=10,small=10,one=1,two=2),193)
        self.assertEqual(sum(result['counts'].values()),193)
        self.assertGreater(result['counts']['big'],150)
        self.assertEqual(result['counts']['small'],10)

    def test_actual_abyss_sizes_have_expected_200_quota(self):
        values=[0,1,154,35,14,0,0,0,6,0,0,0,0,2,0,59,1170,0,10,0]
        sizes={str(i):n for i,n in enumerate(values)}
        out=allocate(sizes,{k:min(10,n) for k,n in sizes.items()},200)['counts']
        self.assertEqual((out['16'],out['2']),(133,18))
        self.assertEqual(sum(out.values()),200)

    def test_largest_remainder_ties_are_deterministic(self):
        result=allocate(dict(b=10,a=10),dict(a=2,b=2),5)
        self.assertEqual(result['counts'],dict(a=3,b=2))
        self.assertEqual(result,allocate(dict(a=10,b=10),dict(b=2,a=2),5))

    def test_zero_and_census_allocations(self):
        self.assertEqual(allocate(dict(z=0),dict(z=0),0)['counts'],dict(z=0))
        self.assertEqual(allocate(dict(a=3,b=9),dict(a=3,b=5),12)['counts'],dict(a=3,b=9))

    def test_invalid_or_infeasible_constraints_fail(self):
        cases=[(dict(a=10),dict(a=5),4),(dict(a=10),dict(a=5),11),
               (dict(a=10),dict(a=11),10),(dict(a=True),dict(a=0),1),
               (dict(a=10),dict(b=2),5),(dict(a=10),dict(a=2),5.5)]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(GateError):allocate(*args)

    def test_every_old_ID_is_retained_in_the_same_prefix(self):
        frame,base,allocation=self.fixture();draw=extend_draw(frame,base,allocation)
        for mode,vs in draw['samples'].items():
            self.assertEqual(sum(x['m'] for x in vs.values()),20)
            for bv,x in vs.items():
                previous=base['samples'][mode][bv]
                self.assertEqual(x['ids'][:previous['m']],previous['ids'])
                self.assertEqual(x['added_m'],x['m']-previous['m'])
                self.assertEqual(len(set(x['ids'])),x['m'])

    def test_combined_sample_weights_recomputed_for_old_and_new_comments(self):
        frame,base,allocation=self.fixture();draw=extend_draw(frame,base,allocation)
        for mode in MODES:
            x=draw['samples'][mode][mode+'big']
            self.assertEqual(x['relative_weight'],50/15)
            self.assertEqual(x['inclusion_probability'],15/50)
            self.assertNotEqual(x['relative_weight'],base['samples'][mode][mode+'big']['relative_weight'])

    def test_replay_is_exact_and_modified_IDs_fail(self):
        frame,base,allocation=self.fixture();draw=extend_draw(frame,base,allocation)
        verify_extension(frame,base,allocation,draw)
        self.assertEqual(draw,extend_draw(frame,base,allocation))
        altered=copy.deepcopy(draw);altered['samples']['abyss']['abyssbig']['ids'][-1]='tampered'
        with self.assertRaisesRegex(GateError,'not_replayable'):verify_extension(frame,base,allocation,altered)

    def test_quota_cannot_discard_originals_or_replace_sources(self):
        frame,base,allocation=self.fixture()
        altered=copy.deepcopy(allocation);altered['abyss']['counts']['abyssbig']=9
        with self.assertRaisesRegex(GateError,'drop_original'):extend_draw(frame,base,altered)
        altered=copy.deepcopy(allocation);del altered['abyss']['counts']['abysszero']
        with self.assertRaisesRegex(GateError,'video_inventory'):extend_draw(frame,base,altered)

    def test_census_extension_preserves_the_same_order(self):
        frame,base,_=self.fixture()
        allocation={m:allocate({b:x['N'] for b,x in vs.items()},{b:x['m'] for b,x in vs.items()},55)
                    for m,vs in base['samples'].items()}
        draw=extend_draw(frame,base,allocation)
        self.assertTrue(all(x['m']==x['N'] for vs in draw['samples'].values() for x in vs.values()))
