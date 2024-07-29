from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import CustomUser


class AuthenticationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("register")
        self.login_url = reverse("token_obtain_pair")
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        }

    def test_user_registration(self):
        response = self.client.post(self.register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CustomUser.objects.filter(username="testuser").exists())

    def test_user_login(self):
        # First, create a user
        CustomUser.objects.create_user(**self.user_data)

        # Attempt to log in
        response = self.client.post(
            self.login_url,
            {
                "username": self.user_data["username"],
                "password": self.user_data["password"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_verification(self):
        # First, create a user and get tokens
        CustomUser.objects.create_user(**self.user_data)
        response = self.client.post(
            self.login_url,
            {
                "username": self.user_data["username"],
                "password": self.user_data["password"],
            },
            format="json",
        )
        access_token = response.data["access"]

        # Verify the token
        verify_url = reverse("verify_token")
        response = self.client.post(verify_url, {"token": access_token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
