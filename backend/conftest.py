"""Pytest fixtures shared across the test suite."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_user(
        email="admin@test.local",
        password="pass12345!",
        full_name="Admin Tester",
        role="admin",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def manager_user(db):
    User = get_user_model()
    return User.objects.create_user(
        email="manager@test.local",
        password="pass12345!",
        full_name="Manager Tester",
        role="manager",
    )


@pytest.fixture
def auth_client(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    return api_client
