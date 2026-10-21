"""
Backend API Tests for ChessZen Classes - Analytics Endpoints
Tests visitor tracking and admin analytics dashboard endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@chesszen.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChessZen@Admin2024")


@pytest.fixture
def authenticated_session():
    """Create an authenticated session for admin endpoints"""
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return session


class TestVisitorTracking:
    """Test public visitor tracking endpoint - POST /api/track"""
    
    def test_track_visitor_new(self):
        """Test tracking a new visitor"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/track", json={
            "page": "/",
            "referrer": "https://google.com"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["tracked", "updated"]
        
        # Check if cookie was set
        cookies = session.cookies.get_dict()
        assert "_cz_vid" in cookies, "Visitor cookie _cz_vid should be set"
        print(f"✓ Visitor tracked, status: {data['status']}, cookie set: _cz_vid")
    
    def test_track_visitor_returning(self):
        """Test tracking a returning visitor (same session)"""
        session = requests.Session()
        
        # First visit
        response1 = session.post(f"{BASE_URL}/api/track", json={
            "page": "/",
            "referrer": None
        })
        assert response1.status_code == 200
        
        # Second visit same day - should update
        response2 = session.post(f"{BASE_URL}/api/track", json={
            "page": "/about",
            "referrer": None
        })
        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "updated", "Returning visitor should get 'updated' status"
        print(f"✓ Returning visitor tracked, status: {data['status']}")
    
    def test_track_visitor_no_auth_required(self):
        """Test that tracking endpoint doesn't require authentication"""
        response = requests.post(f"{BASE_URL}/api/track", json={
            "page": "/programs",
            "referrer": None
        })
        assert response.status_code == 200
        print("✓ Tracking endpoint is public (no auth required)")


class TestAnalyticsOverview:
    """Test GET /api/admin/analytics/overview"""
    
    def test_overview_requires_auth(self):
        """Test that overview endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/overview")
        assert response.status_code == 401
        print("✓ Analytics overview correctly requires authentication")
    
    def test_overview_returns_kpis(self, authenticated_session):
        """Test overview returns all KPI fields"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/overview")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all required fields
        required_fields = ["today", "this_week", "prev_week", "week_change", 
                          "this_month", "prev_month", "month_change", "total"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["today"], int)
        assert isinstance(data["this_week"], int)
        assert isinstance(data["total"], int)
        assert isinstance(data["week_change"], (int, float))
        assert isinstance(data["month_change"], (int, float))
        
        print(f"✓ Analytics overview: today={data['today']}, week={data['this_week']}, month={data['this_month']}, total={data['total']}")
        print(f"  Week change: {data['week_change']}%, Month change: {data['month_change']}%")


class TestAnalyticsDaily:
    """Test GET /api/admin/analytics/daily"""
    
    def test_daily_requires_auth(self):
        """Test that daily endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/daily?days=7")
        assert response.status_code == 401
        print("✓ Analytics daily correctly requires authentication")
    
    def test_daily_default_days(self, authenticated_session):
        """Test daily analytics with default days parameter"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/daily")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 30, "Default should return 30 days"
        
        # Verify structure
        for entry in data:
            assert "date" in entry
            assert "visitors" in entry
            assert isinstance(entry["visitors"], int)
        
        print(f"✓ Daily analytics: {len(data)} days returned")
    
    def test_daily_custom_days(self, authenticated_session):
        """Test daily analytics with custom days parameter"""
        for days in [7, 14, 30, 60]:
            response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/daily?days={days}")
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == days, f"Should return {days} days"
        
        print("✓ Daily analytics works with custom days: 7, 14, 30, 60")


class TestAnalyticsWeekly:
    """Test GET /api/admin/analytics/weekly"""
    
    def test_weekly_requires_auth(self):
        """Test that weekly endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/weekly")
        assert response.status_code == 401
        print("✓ Analytics weekly correctly requires authentication")
    
    def test_weekly_returns_data(self, authenticated_session):
        """Test weekly analytics returns proper structure"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/weekly")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 8, "Default should return 8 weeks"
        
        # Verify structure
        for entry in data:
            assert "week" in entry
            assert "visitors" in entry
            assert "start" in entry
            assert isinstance(entry["visitors"], int)
        
        print(f"✓ Weekly analytics: {len(data)} weeks returned")


class TestAnalyticsTopPages:
    """Test GET /api/admin/analytics/top-pages"""
    
    def test_top_pages_requires_auth(self):
        """Test that top-pages endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/top-pages")
        assert response.status_code == 401
        print("✓ Analytics top-pages correctly requires authentication")
    
    def test_top_pages_returns_data(self, authenticated_session):
        """Test top-pages returns proper structure"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/top-pages?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10, "Should return max 10 pages"
        
        # Verify structure if data exists
        for entry in data:
            assert "page" in entry
            assert "views" in entry
            assert isinstance(entry["views"], int)
        
        print(f"✓ Top pages: {len(data)} pages returned")


class TestAnalyticsPeakHours:
    """Test GET /api/admin/analytics/peak-hours"""
    
    def test_peak_hours_requires_auth(self):
        """Test that peak-hours endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/peak-hours")
        assert response.status_code == 401
        print("✓ Analytics peak-hours correctly requires authentication")
    
    def test_peak_hours_returns_24_entries(self, authenticated_session):
        """Test peak-hours returns 24 hour entries"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/peak-hours?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 24, "Should return 24 hour entries"
        
        # Verify structure
        for entry in data:
            assert "hour" in entry
            assert "h" in entry
            assert "visitors" in entry
            assert isinstance(entry["h"], int)
            assert 0 <= entry["h"] <= 23
        
        print(f"✓ Peak hours: {len(data)} hour entries returned")


class TestAnalyticsDevices:
    """Test GET /api/admin/analytics/devices"""
    
    def test_devices_requires_auth(self):
        """Test that devices endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/devices")
        assert response.status_code == 401
        print("✓ Analytics devices correctly requires authentication")
    
    def test_devices_returns_breakdown(self, authenticated_session):
        """Test devices returns device breakdown"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/devices?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Verify structure if data exists
        for entry in data:
            assert "device" in entry
            assert "count" in entry
            assert entry["device"] in ["Desktop", "Mobile"]
            assert isinstance(entry["count"], int)
        
        print(f"✓ Device breakdown: {len(data)} device types returned")


class TestAnalyticsExport:
    """Test GET /api/admin/analytics/export"""
    
    def test_export_requires_auth(self):
        """Test that export endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/export")
        assert response.status_code == 401
        print("✓ Analytics export correctly requires authentication")
    
    def test_export_returns_csv(self, authenticated_session):
        """Test export returns CSV file"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/analytics/export?days=30")
        assert response.status_code == 200
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected CSV, got: {content_type}"
        
        # Check content disposition header
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition
        assert "filename=" in content_disposition
        
        # Verify CSV content
        csv_content = response.text
        lines = csv_content.strip().split("\n")
        assert len(lines) >= 1, "CSV should have at least header row"
        
        # Check header row
        header = lines[0]
        expected_columns = ["Date", "Time", "Visitor ID", "Device", "Pages Visited", "Referrer"]
        for col in expected_columns:
            assert col in header, f"Missing column: {col}"
        
        print(f"✓ CSV export: {len(lines)} rows (including header)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
