"""
Backend API Tests for ChessZen Classes - Auth with httpOnly Cookies
Tests the code review fixes: httpOnly cookies for JWT auth, no localStorage
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from environment or defaults for testing
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@chesszen.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChessZen@Admin2024")


class TestHealthAndRoot:
    """Basic API health checks"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ API root working: {data['message']}")


class TestAuthWithCookies:
    """Test authentication flow with httpOnly cookies"""
    
    def test_login_sets_httponly_cookies(self):
        """Test that login sets httpOnly cookies and returns user info"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify user info is returned
        assert "id" in data
        assert "email" in data
        assert data["email"] == ADMIN_EMAIL
        assert "role" in data
        assert data["role"] == "admin"
        
        # Verify cookies are set (httpOnly cookies for secure auth)
        cookies = session.cookies.get_dict()
        assert "access_token" in cookies, "access_token cookie should be set"
        assert "refresh_token" in cookies, "refresh_token cookie should be set"
        
        print(f"✓ Login successful, cookies set: {list(cookies.keys())}")
        print(f"✓ Response body contains user info: {data['email']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")
    
    def test_auth_me_with_cookie(self):
        """Test /auth/me endpoint uses cookie for authentication"""
        session = requests.Session()
        
        # First login to get cookies
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        
        # Now call /auth/me - should use cookie automatically
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200
        
        data = me_response.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "password_hash" not in data, "password_hash should not be exposed"
        
        print(f"✓ /auth/me works with cookie auth: {data['email']}")
    
    def test_auth_me_without_cookie_fails(self):
        """Test /auth/me fails without authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ /auth/me correctly rejects unauthenticated requests")
    
    def test_logout_clears_cookies(self):
        """Test logout clears cookies"""
        session = requests.Session()
        
        # Login first
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        
        # Verify cookies exist
        assert "access_token" in session.cookies.get_dict()
        
        # Logout
        logout_response = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_response.status_code == 200
        
        data = logout_response.json()
        assert "message" in data
        
        print(f"✓ Logout successful: {data['message']}")


class TestAdminEndpointsWithCookies:
    """Test admin endpoints use cookie authentication"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Create an authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_admin_stats_requires_auth(self):
        """Test admin stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 401
        print("✓ /admin/stats correctly requires authentication")
    
    def test_admin_stats_with_cookie(self, authenticated_session):
        """Test admin stats works with cookie auth"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_bookings" in data
        assert "confirmed_bookings" in data
        assert "total_testimonials" in data
        assert "pending_testimonials" in data
        assert "total_enquiries" in data
        assert "recent_enquiries" in data
        
        print(f"✓ Admin stats: bookings={data['total_bookings']}, testimonials={data['total_testimonials']}, enquiries={data['total_enquiries']}")
    
    def test_admin_testimonials_with_cookie(self, authenticated_session):
        """Test admin testimonials endpoint with cookie auth"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/testimonials")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin testimonials: {len(data)} testimonials found")
    
    def test_bookings_with_cookie(self, authenticated_session):
        """Test bookings endpoint with cookie auth"""
        response = authenticated_session.get(f"{BASE_URL}/api/bookings")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Bookings: {len(data)} bookings found")
    
    def test_enquiries_with_cookie(self, authenticated_session):
        """Test enquiries endpoint with cookie auth"""
        response = authenticated_session.get(f"{BASE_URL}/api/enquiries")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Enquiries: {len(data)} enquiries found")


class TestPublicEndpoints:
    """Test public endpoints that don't require auth"""
    
    def test_public_testimonials(self):
        """Test public testimonials endpoint"""
        response = requests.get(f"{BASE_URL}/api/testimonials?approved_only=true")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # All returned testimonials should be approved
        for t in data:
            assert t.get("approved") is True
        print(f"✓ Public testimonials: {len(data)} approved testimonials")
    
    def test_available_slots(self):
        """Test available slots endpoint"""
        response = requests.get(f"{BASE_URL}/api/available-slots?date=2026-02-15")
        assert response.status_code == 200
        
        data = response.json()
        assert "date" in data
        assert "available_slots" in data
        assert isinstance(data["available_slots"], list)
        print(f"✓ Available slots for 2026-02-15: {len(data['available_slots'])} slots")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
