"""Numerical checks against enumerated finite populations and domain identities."""
import itertools
import unittest
from estimate_reviewed_snapshot import ratio, indicators


class SnapshotEstimationTests(unittest.TestCase):
    def test_stratified_known_denominator_exact_enumeration(self):
        pops=([1,0,0],[1,1,0,0]);est=[];var=[]
        for a,b in itertools.product(itertools.combinations(range(3),2),itertools.combinations(range(4),2)):
            clusters=[dict(N=len(pop),values=[(pop[i],1,0) for i in indices]) for pop,indices in zip(pops,(a,b))]
            result=ratio(clusters);est.append(result['proportion']);var.append(result['sampling_variance'])
        truth=3/7
        self.assertAlmostEqual(sum(est)/len(est),truth)
        true_sampling_variance=sum((x-truth)**2 for x in est)/len(est)
        self.assertAlmostEqual(sum(var)/len(var),true_sampling_variance)

    def test_domain_zeros_stay_in_the_original_sample(self):
        result=ratio([dict(N=4,values=[(1,1,0),(0,0,0),(0,1,0)])])
        self.assertAlmostEqual(result['proportion'],.5)
        self.assertAlmostEqual(result['weighted_known_denominator'],8/3)
        self.assertAlmostEqual(result['sampling_variance'],.046875)

    def test_unknown_bounds_are_not_a_confidence_interval(self):
        result=ratio([dict(N=3,values=[(1,1,0),(0,1,0),(0,0,1)])])
        self.assertEqual(result['unknown_extreme_scenario_bounds'],[1/3,2/3])
        self.assertEqual(result['interval95'],[.5,.5])
        self.assertFalse(result['bounds_include_sampling_error'])

    def test_no_sample_hits_is_not_proof_of_absence(self):
        result=ratio([dict(N=100,values=[(0,1,0)]*10)])
        self.assertEqual(result['interval95'],[0.,1.])
        self.assertFalse(result['precision_target_met'])

    def test_zero_denominator_returns_no_estimate(self):
        result=ratio([dict(N=100,values=[(0,0,1)]*10)])
        self.assertIsNone(result['proportion'])

    def test_singleton_census_is_valid_but_singleton_sample_is_not(self):
        result=ratio([dict(N=1,values=[(1,1,0)])])
        self.assertEqual(result['interval95'],[1.,1.])
        with self.assertRaises(AssertionError):ratio([dict(N=5,values=[(1,1,0)])])

    def test_problem_uncertainty_does_not_erase_a_known_discussion_topic(self):
        row=dict(relevance='related',problem_status='unknown',problem_themes='',theme_status='known',themes='roster_build')
        self.assertEqual(indicators(row,'reported_problem_any'),(0,0,1))
        self.assertEqual(indicators(row,'themes.roster_build'),(1,1,0))

    def test_nonself_advice_is_not_a_reported_problem(self):
        row=dict(relevance='related',problem_status='none_explicit',problem_themes='',theme_status='known',themes='roster_build')
        self.assertEqual(indicators(row,'reported_problem_any'),(0,1,0))


if __name__=='__main__':unittest.main()
