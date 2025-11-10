def search_issue_by_seed(repo, tok, seed_id):
    """
    Verifica se já existe issue com este seed_id sem usar o endpoint de Search
    (evita 403 em organizações). Faz paginação em /repos/{repo}/issues?state=all.
    """
    url = f"https://api.github.com/repos/{repo}/issues"
    page = 1
    needle = f"seed_id:{seed_id}"
    while True:
        r = requests.get(
            url,
            headers=headers(tok),
            params={"state": "all", "per_page": 100, "page": page},
        )
        r.raise_for_status()
        items = r.json()
        if not items:
            break
        for it in items:
            # Ignora PRs (a API de issues lista PRs também)
            if "pull_request" in it:
                continue
            body = (it.get("body") or "")
            if needle in body:
                return True, it["number"]
        page += 1
    return False, 0
