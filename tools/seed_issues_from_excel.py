#!/usr/bin/env python3
import argparse, hashlib, json, os, sys, time
from datetime import datetime
import pandas as pd, requests
REQ_COLS_MIN = ["Semana","SQUAD","Tarefa"]
def headers(tok): return {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
def die(msg): print(f"❌ {msg}"); sys.exit(1)
def load_excel(path):
    try: df = pd.read_excel(path)
    except Exception as e: die(f"Falha lendo {path}: {e}")
    miss=[c for c in REQ_COLS_MIN if c not in df.columns]
    if miss: die(f"Colunas mínimas ausentes: {miss}\nEncontradas: {list(df.columns)}")
    return df.fillna("")
def ensure_labels(repo, tok, labels):
    url=f"https://api.github.com/repos/{repo}/labels"; existing=set(); page=1
    while True:
        r=requests.get(url, headers=headers(tok), params={"per_page":100,"page":page}); r.raise_for_status()
        items=r.json(); 
        if not items: break
        for it in items: existing.add(it["name"]); page+=1
    for name in labels:
        if name not in existing: requests.post(url, headers=headers(tok), json={"name":name,"color":"ededed"})
def search_issue_by_seed(repo, tok, seed_id):
    q=f'repo:{repo} "{seed_id}" in:body'; r=requests.get("https://api.github.com/search/issues", headers=headers(tok), params={"q":q}); r.raise_for_status()
    js=r.json()
    if js.get("total_count",0)>0: it=js["items"][0]; return True, it["number"]
    return False,0
def create_issue(repo,tok,title,body,labels,assignees):
    url=f"https://api.github.com/repos/{repo}/issues"; payload={"title":title,"body":body,"labels":labels}
    if assignees: payload["assignees"]=assignees
    r=requests.post(url, headers=headers(tok), json=payload); r.raise_for_status(); return r.json()["number"]
def build_labels(row):
    labs=[]
    if row.get("Semana"): labs.append(f"Semana:{row['Semana']}")
    if row.get("SQUAD"): labs.append(str(row["SQUAD"]).strip())
    if row.get("Id Aluno"): labs.append(f"IdAluno:{row['Id Aluno']}")
    if str(row.get("IA","")).upper() in ("COMIA","SEMIA"): labs.append(f"IA:{str(row['IA']).upper()}")
    if row.get("Papel"): labs.append(f"Papel:{row['Papel']}".upper())
    if row.get("Tipo"): labs.append(f"Tipo:{str(row['Tipo']).lower()}")
    if row.get("Labels Sugeridos"): labs += [s.strip() for s in str(row["Labels Sugeridos"]).split(",") if s.strip()]
    return sorted(set(labs))
def build_body(row, seed_id):
    def g(k): return row.get(k,"")
    bod=[]
    for k in ["Descrição","Entregáveis","Critérios de Aceite","Arquivos Sugeridos","Comando de Verificação","Observações"]:
        if g(k): bod.append(f"**{k}:**\n{g(k)}")
    meta=[]
    for k in ["Projeto","Módulo","Semana","SQUAD","Papel","Id Aluno","IA","Tipo","Dificuldade","Peso","Deadline","Revisor"]:
        if g(k): meta.append(f"**{k}:** {g(k)}")
    if meta: bod.append("\n".join(meta))
    bod.append(f"\n<!-- seed_id:{seed_id} -->")
    return "\n\n".join(bod)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=False); ap.add_argument("--token",required=False)
    ap.add_argument("--file",default="backlog/ISSUE.xlsx"); ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    repo=args.repo or os.getenv("GITHUB_REPOSITORY") or die("Defina --repo ou GITHUB_REPOSITORY")
    tok=args.token or os.getenv("GITHUB_TOKEN") or die("Defina --token ou GITHUB_TOKEN")
    df=load_excel(args.file); rows=df.to_dict(orient="records")
    all_labels=set(); 
    for r in rows: all_labels.update(build_labels(r))
    ensure_labels(repo,tok,all_labels)
    created,skipped=[],[]
    for r in rows:
        seed_src=json.dumps({k: r.get(k,"") for k in ["Semana","SQUAD","Id Aluno","Papel","IA","Tarefa"]}, ensure_ascii=False)
        seed_id=hashlib.sha1(seed_src.encode("utf-8")).hexdigest()[:12]
        exists,num=search_issue_by_seed(repo,tok,seed_id)
        if exists: skipped.append({"t":r.get("Tarefa",""),"n":num,"why":"dup"}); continue
        title=r.get("Título do PR") or r.get("Tarefa") or "Tarefa"
        labels=build_labels(r); assignees=[]; body=build_body(r,seed_id)
        if args.dry_run: print(f"[DRY-RUN] Criaria issue: '{title}' | labels={labels}"); continue
        try: num=create_issue(repo,tok,title,body,labels,assignees); created.append(num); time.sleep(0.2)
        except requests.HTTPError as e: print(f"⚠️ Falha ao criar issue '{title}': {e.response.text}")
    stamp=datetime.utcnow().strftime("%Y%m%d-%H%M"); log={"repo":repo,"created":created,"skipped":skipped,"ts":stamp}
    with open(f"seed-log-{stamp}.json","w",encoding="utf-8") as f: json.dump(log,f,ensure_ascii=False,indent=2)
    print(f"✅ Seed concluído. Criadas: {len(created)} | Puladas: {len(skipped)}")
if __name__=="__main__": main()
