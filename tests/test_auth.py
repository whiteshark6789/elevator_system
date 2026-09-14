import unittest
from unittest.mock import patch, MagicMock
import datetime
import sys
import os

# Append the backend directory to path so we can import app
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Mock psycopg2 before app starts to avoid db connection pool failure in test environment
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.pool'] = MagicMock()

import app
from db import DatabaseManager

class SecureElevatorAccessTestCase(unittest.TestCase):
    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['WTF_CSRF_ENABLED'] = False
        app.app.config['SECRET_KEY'] = 'test-key'
        self.client = app.app.test_client()
        
    @patch('app.DatabaseManager.execute_one')
    def test_login_page_loads(self, mock_execute):
        """Verifies the login page HTML loads successfully."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Authentication Required', response.data)
        
    @patch('app.DatabaseManager.execute_one')
    def test_elevator_panel_redirect_unauthorized(self, mock_execute):
        """Verifies accessing elevator screen redirects to login if unauthorized."""
        response = self.client.get('/elevator')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    @patch('app.DatabaseManager.execute_one')
    def test_password_auth_rate_limit(self, mock_execute_one):
        """Tests rate limits lock account after 5 consecutive failures (REQ-55)."""
        # Mock that recent failures count is 5
        mock_execute_one.side_effect = [
            (1, "testuser", "pwd_hash", "Test User", "resident", True), # First fetch
            [5] # Count of failures (returned for second query)
        ]
        
        response = self.client.post('/api/auth/password', json={
            "username": "testuser",
            "password": "WrongPassword1"
        })
        self.assertEqual(response.status_code, 429)
        self.assertIn(b'Account is temporarily locked', response.data)

    @patch('app.DatabaseManager.execute_one')
    def test_otp_validation_success(self, mock_execute_one):
        """Tests successful visitor OTP validation (REQ-13, REQ-16)."""
        future_expiry = datetime.datetime.now() + datetime.timedelta(minutes=15)
        # Mock active OTP returned from database
        mock_execute_one.return_value = (10, [1, 2], 1)  # (otp_id, allowed_floors, requested_by)
        
        response = self.client.post('/api/auth/otp', json={
            "otp_code": "999888"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'success', response.data)
        self.assertIn(b'/elevator', response.data)
        
    @patch('app.DatabaseManager.execute_one')
    @patch('app.DatabaseManager.execute_query')
    def test_create_user_complexity_validation(self, mock_execute_query, mock_execute_one):
        """Tests that password complexity rules are strictly enforced during user creation."""
        # Setup admin session
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'admin'
            
        # Weak password (no number, short)
        response = self.client.post('/api/admin/users/create', json={
            "username": "newuser",
            "password": "weak",
            "name": "New Resident",
            "role": "resident",
            "floors": [1]
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Password must be at least 8 characters long', response.data)
        
        # Weak password (missing uppercase)
        response = self.client.post('/api/admin/users/create', json={
            "username": "newuser",
            "password": "weakpassword1",
            "name": "New Resident",
            "role": "resident",
            "floors": [1]
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Password must be at least 8 characters long', response.data)

    @patch('app.DatabaseManager.execute_one')
    def test_edit_permissions_during_auth_blocked(self, mock_execute_one):
        """Checks floor permissions can't be edited for users mid-authentication (REQ-20)."""
        # Setup admin session
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'admin'
            
        # Mock that user had a recent login in the last 10 seconds (returns 1)
        mock_execute_one.return_value = (1,)
        
        response = self.client.post('/api/admin/users/update_permissions', json={
            "user_id": 4,
            "floors": [1, 2]
        })
        self.assertEqual(response.status_code, 423)
        self.assertIn(b'User is currently authenticating', response.data)

if __name__ == '__main__':
    unittest.main()
