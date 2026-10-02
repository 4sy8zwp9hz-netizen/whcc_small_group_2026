"""Lazy server authentication: explicit local key or runtime ADC."""
def credentials_for(path="", readonly=False):
    scope = "https://www.googleapis.com/auth/spreadsheets" + (".readonly" if readonly else "")
    if path:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(path, scopes=[scope])
    import google.auth
    return google.auth.default(scopes=[scope])[0]
