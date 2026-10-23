import pytest
from django.db import IntegrityError, connection, transaction

from accounts.models import EmergencyContact, User, UserStatus


@pytest.mark.django_db
def test_user_logs_in_with_email_and_password_is_bcrypt(make_user):
    user = make_user(email="Sora@Example.com")
    assert user.email == "sora@example.com"  # normalised
    assert user.check_password("Camp1ng!Pass")
    assert user.password.startswith("bcrypt_sha256$")


@pytest.mark.django_db
def test_create_superuser_is_staff_and_has_consent():
    admin = User.objects.create_superuser(email="admin@example.com", password="x-Strong-123")
    assert admin.is_staff and admin.is_superuser
    assert admin.pdpa_consent_at is not None


@pytest.mark.django_db
def test_email_is_unique(make_user):
    make_user(email="dup@example.com")
    with pytest.raises(IntegrityError):
        make_user(email="dup@example.com")


@pytest.mark.django_db
def test_many_users_without_phone_allowed(make_user):
    a, b = make_user(phone=""), make_user(phone="")
    assert a.phone is None and b.phone is None


@pytest.mark.django_db
@pytest.mark.parametrize("status", [UserStatus.SUSPENDED, UserStatus.BANNED, UserStatus.INACTIVE])
def test_non_active_status_blocks_login(make_user, status):
    assert make_user(status=status).is_active is False


@pytest.mark.django_db
def test_deleted_status_requires_deleted_at(make_user):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_user(status=UserStatus.DELETED)  # no deleted_at


@pytest.mark.django_db
def test_emergency_contact_is_encrypted_at_rest(user):
    EmergencyContact.objects.create(
        user=user, name="Mya Mya", phone="+66812345678", relationship="sister"
    )
    with connection.cursor() as cur:
        cur.execute("SELECT name, phone FROM emergency_contacts WHERE user_id = %s", [user.id])
        raw_name, raw_phone = cur.fetchone()
    assert "Mya" not in raw_name and "812345678" not in raw_phone
    contact = EmergencyContact.objects.get(user=user)
    assert contact.name == "Mya Mya" and contact.phone == "+66812345678"


@pytest.mark.django_db
def test_emergency_contact_one_per_user(user):
    EmergencyContact.objects.create(user=user, name="A", phone="1", relationship="x")
    with pytest.raises(IntegrityError):
        EmergencyContact.objects.create(user=user, name="B", phone="2", relationship="y")
