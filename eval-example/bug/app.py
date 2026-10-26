def latest(rows):
    return list({r['id']:r for r in rows}.values())
