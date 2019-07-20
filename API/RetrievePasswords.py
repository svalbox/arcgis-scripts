import keyring, getpass

def Passwords(service,username):
    if keyring.get_password(service, username) is None:
        keyring.set_password(service, username, getpass.getpass())
    return keyring.get_password(service, username)

Passwords('SketchFab','svalbox')