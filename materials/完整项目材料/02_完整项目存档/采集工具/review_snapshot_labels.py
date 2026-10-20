"""Read-only display for a second AI review; not an independent/human recode."""
import json, sys
from continue_snapshot_coding import S, setup, ancestors, public_text

def data():
    f,d,L,v,q=setup()
    rows=S.frozen('small_snapshot_coding_full_proposals_001.json')['rows']
    return f,d,L,v,rows

if __name__=='__main__':
    f,d,L,v,rows=data();cmd=sys.argv[1]
    if cmd=='show':
        start=int(sys.argv[2]);count=int(sys.argv[3]);last=None
        for k,p in enumerate(rows,start=1):
            if not start<=k<start+count:continue
            raw=L[p['id']]
            if last!=p['bvid']:
                print(json.dumps(dict(source=p['bvid'],mode=p['mode'],title=v[p['bvid']]['title']),ensure_ascii=False));last=p['bvid']
            print(json.dumps(dict(k=k,id=p['id'],text=public_text(raw['text']),rel=p['relevance'],themes=p['themes'],self=p['self_experience_themes'],kind=p['experience_kind'],problem=p['problem_themes'],flags=p['content_flags']),ensure_ascii=False))
    elif cmd=='detail':
        for token in sys.argv[2:]:
            p=next(r for r in rows if r['id']==token);raw=L[token]
            print(json.dumps(dict(proposal=p,text=public_text(raw['text']),title=v[p['bvid']]['title'],ancestors=ancestors(raw,L)),ensure_ascii=False))
    elif cmd=='thread':
        for token in sys.argv[2:]:
            r=L[token];root=r['root_id'] if r['root_id']!='0' else token
            print(json.dumps(dict(query=token,root=root,thread=[dict(id=a['id'],parent=a['parent_id'],text=public_text(a['text'])) for a in f['comments'] if a['id']==root or a['root_id']==root]),ensure_ascii=False))
