def latest(rows):
    winners={}
    for row in rows:
        if row['id'] not in winners or row['version']>=winners[row['id']]['version']:
            winners[row['id']]=row
    return list(winners.values())
