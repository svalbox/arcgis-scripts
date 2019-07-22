import keyring, getpass

def Passwords(service,username):
    '''
    :param service: Name of the service for which a password has been stored
    :param username: Username for the service specified above
    :return: Password for the username specified above, if None, prompts the user to specify the password
    '''
    if keyring.get_password(service, username) is None:
        keyring.set_password(service, username, getpass.getpass())
    return keyring.get_password(service, username)

# Passwords('SketchFab','svalbox')