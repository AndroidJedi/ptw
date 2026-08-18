from __future__ import annotations
import os,re
from pathlib import Path
import psycopg

ROOT=Path(os.getenv("SPEC_ROOT","/app/ideaGeneration/docs"))
def seed(url: str):
    mission=(ROOT/"TASK_450M_5Y.md").read_text()
    files=sorted((ROOT/"contexts").glob("C*.md"))
    if len(files)!=10: raise RuntimeError(f"expected 10 context files, got {len(files)}")
    with psycopg.connect(url) as c:
        row=c.execute("INSERT INTO missions(code,name,task_text,auto_enabled) VALUES('MISSION_450M_5Y','Build a Company That Could Be Sold for $450M Within 5 Years',%s,false) ON CONFLICT(code) DO UPDATE SET name=excluded.name RETURNING id",(mission,)).fetchone()
        for order,path in enumerate(files,1):
            text=path.read_text(); code=re.search(r'\*\*Code:\*\* `(C\d\d)`',text).group(1); name=re.search(r'^# C\d\d — (.+)$',text,re.M).group(1)
            rec=c.execute("INSERT INTO contexts(code,name,prompt_text,sort_order) VALUES(%s,%s,%s,%s) ON CONFLICT(code) DO UPDATE SET sort_order=excluded.sort_order RETURNING id,version,name,prompt_text",(code,name,text,order)).fetchone()
            c.execute("INSERT INTO context_revisions(context_id,version,name,prompt_text,changed_by,change_note) VALUES(%s,%s,%s,%s,'system','initial seed') ON CONFLICT DO NOTHING",rec)
        count=c.execute("SELECT count(*) FROM contexts WHERE active").fetchone()[0]
        if count!=10: raise RuntimeError(f"active context count is {count}")
if __name__=='__main__': seed(os.environ['DATABASE_URL'])
