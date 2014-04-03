import base64
import hashlib
import os
import re
import sys

from django.contrib.auth.models import User
from django.db import IntegrityError



def _email_to_username(email):
    email = email.lower()
    converted = email.encode('utf8', 'ignore')
    return base64.urlsafe_b64encode(hashlib.sha256(converted).digest())[:30]


def get_user(email, queryset=None):
    if queryset is None:
        queryset = User.objects
    return queryset.get(username=_email_to_username(email))


def user_exists(email, queryset=None):
    try:
        get_user(email, queryset)
    except User.DoesNotExist:
        return False
    return True


_DUPLICATE_USERNAME_ERRORS = (
    'column username is not unique',
    'duplicate key value violates unique constraint "auth_user_username_key"\n'
)


def create_user(email, password=None, is_staff=None, is_active=None):
    try:
        user = User.objects.create_user(email, email, password)
    except IntegrityError, err:
        regexp = '|'.join(re.escape(e) for e in _DUPLICATE_USERNAME_ERRORS)
        if re.match(regexp, err.message):
            raise IntegrityError('user email is not unique')
        raise

    if is_active is not None or is_staff is not None:
        if is_active is not None:
            user.is_active = is_active
        if is_staff is not None:
            user.is_staff = is_staff
        user.save()
    return user


def create_superuser(email, password):
    return User.objects.create_superuser(email, email, password)


def migrate_usernames(stream=None, quiet=False):
    stream = stream or (quiet and open(os.devnull, 'w') or sys.stdout)

    # Check all users can be migrated before applying migration
    emails = set()
    errors = []
    for user in User.objects.all():
        if not user.email:
            errors.append("Cannot convert user '%s' because email is not "
                          "set." % (user._username, ))
        elif user.email.lower() in emails:
            errors.append("Cannot convert user '%s' because email '%s' "
                          "already exists." % (user._username, user.email))
        else:
            emails.add(user.email.lower())

    # Cannot migrate.
    if errors:
        [stream.write(error + '\n') for error in errors]
        raise Exception('django-email-as-username migration failed.')

    # Can migrate just fine.
    total = User.objects.count()
    for user in User.objects.all():
        user.username = _email_to_username(user.email)
        user.save()

    stream.write("Successfully migrated usernames for all %d users\n"
                 % (total, ))
