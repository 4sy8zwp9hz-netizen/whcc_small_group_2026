"""Canonical A1 tab identity; quote spelling must not create new meetings."""
def source_title(source_range):
    title = source_range.rsplit("!", 1)[0]
    if len(title) >= 2 and title.startswith("'") and title.endswith("'"):
        return title[1:-1].replace("''", "'")
    return title


def legacy_namespaces(spreadsheet_id, source_range):
    title = source_title(source_range)
    spellings = {source_range.split("!")[0], source_range.rsplit("!", 1)[0], title, "'" + title.replace("'", "''") + "'"}
    return {"google\0" + spreadsheet_id + "\0" + spelling for spelling in spellings}
