"""
Portal API Tests - Student Management Portal
Tests: Dashboard, Batches CRUD, Students CRUD, Holidays
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://chesszen-academy.preview.emergentagent.com')

# Test credentials from environment
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@chesszen.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChessZen@Admin2024")


class TestPortalAuth:
    """Test portal authentication requirements"""
    
    def test_portal_dashboard_requires_auth(self):
        """Dashboard endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/portal/dashboard")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Dashboard requires auth (401)")
    
    def test_portal_batches_requires_auth(self):
        """Batches endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/portal/batches")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Batches requires auth (401)")
    
    def test_portal_students_requires_auth(self):
        """Students endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/portal/students")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Students requires auth (401)")


class TestPortalDashboard:
    """Test dashboard stats endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        print("✓ Logged in successfully")
    
    def test_dashboard_returns_all_fields(self):
        """Dashboard should return total_students, active_students, batch_stats, level_distribution"""
        response = self.session.get(f"{BASE_URL}/api/portal/dashboard")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Check required fields
        assert "total_students" in data, "Missing total_students"
        assert "active_students" in data, "Missing active_students"
        assert "inactive_students" in data, "Missing inactive_students"
        assert "total_batches" in data, "Missing total_batches"
        assert "batch_stats" in data, "Missing batch_stats"
        assert "level_distribution" in data, "Missing level_distribution"
        assert "age_distribution" in data, "Missing age_distribution"
        
        # Validate types
        assert isinstance(data["total_students"], int)
        assert isinstance(data["active_students"], int)
        assert isinstance(data["batch_stats"], list)
        assert isinstance(data["level_distribution"], list)
        
        print(f"✓ Dashboard returns all fields: total_students={data['total_students']}, batches={data['total_batches']}")


class TestPortalBatches:
    """Test batch CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.created_batch_ids = []
    
    def teardown_method(self):
        """Cleanup created batches"""
        for batch_id in self.created_batch_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/portal/batches/{batch_id}")
            except Exception:
                pass
    
    def test_list_batches(self):
        """GET /api/portal/batches - list all batches with student_count"""
        response = self.session.get(f"{BASE_URL}/api/portal/batches")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of batches"
        
        # Check seeded batches exist
        batch_names = [b["name"] for b in data]
        print(f"✓ Listed {len(data)} batches: {batch_names}")
        
        # Verify batch structure
        if len(data) > 0:
            batch = data[0]
            assert "id" in batch, "Missing id"
            assert "name" in batch, "Missing name"
            assert "student_count" in batch, "Missing student_count"
            assert "max_capacity" in batch, "Missing max_capacity"
            print(f"✓ Batch structure valid: {batch['name']} has {batch['student_count']} students")
    
    def test_create_batch(self):
        """POST /api/portal/batches - create new batch"""
        batch_data = {
            "name": f"TEST_Batch_{uuid.uuid4().hex[:6]}",
            "schedule_days": ["Mon", "Wed", "Fri"],
            "schedule_time": "5:00 PM - 6:00 PM",
            "max_capacity": 15
        }
        
        response = self.session.post(f"{BASE_URL}/api/portal/batches", json=batch_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == batch_data["name"]
        assert data["schedule_days"] == batch_data["schedule_days"]
        assert data["schedule_time"] == batch_data["schedule_time"]
        assert data["max_capacity"] == batch_data["max_capacity"]
        assert "id" in data
        assert data["student_count"] == 0
        
        self.created_batch_ids.append(data["id"])
        print(f"✓ Created batch: {data['name']} (id: {data['id']})")
    
    def test_update_batch(self):
        """PUT /api/portal/batches/:id - update batch"""
        # First create a batch
        batch_data = {
            "name": f"TEST_Update_{uuid.uuid4().hex[:6]}",
            "schedule_days": ["Tue"],
            "schedule_time": "4:00 PM",
            "max_capacity": 10
        }
        create_resp = self.session.post(f"{BASE_URL}/api/portal/batches", json=batch_data)
        assert create_resp.status_code == 200
        batch_id = create_resp.json()["id"]
        self.created_batch_ids.append(batch_id)
        
        # Update the batch
        update_data = {
            "name": f"TEST_Updated_{uuid.uuid4().hex[:6]}",
            "max_capacity": 25
        }
        update_resp = self.session.put(f"{BASE_URL}/api/portal/batches/{batch_id}", json=update_data)
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        
        # Verify update
        list_resp = self.session.get(f"{BASE_URL}/api/portal/batches")
        batches = list_resp.json()
        updated_batch = next((b for b in batches if b["id"] == batch_id), None)
        assert updated_batch is not None
        assert updated_batch["name"] == update_data["name"]
        assert updated_batch["max_capacity"] == 25
        
        print(f"✓ Updated batch: {updated_batch['name']}")
    
    def test_delete_batch_without_students(self):
        """DELETE /api/portal/batches/:id - delete batch without students"""
        # Create a batch
        batch_data = {"name": f"TEST_Delete_{uuid.uuid4().hex[:6]}", "max_capacity": 5}
        create_resp = self.session.post(f"{BASE_URL}/api/portal/batches", json=batch_data)
        assert create_resp.status_code == 200
        batch_id = create_resp.json()["id"]
        
        # Delete the batch
        delete_resp = self.session.delete(f"{BASE_URL}/api/portal/batches/{batch_id}")
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}: {delete_resp.text}"
        
        # Verify deletion
        list_resp = self.session.get(f"{BASE_URL}/api/portal/batches")
        batches = list_resp.json()
        assert not any(b["id"] == batch_id for b in batches), "Batch should be deleted"
        
        print(f"✓ Deleted batch successfully")
    
    def test_delete_batch_with_students_fails(self):
        """DELETE /api/portal/batches/:id - should fail if students assigned"""
        # Create a batch
        batch_data = {"name": f"TEST_NoDelete_{uuid.uuid4().hex[:6]}", "max_capacity": 10}
        create_resp = self.session.post(f"{BASE_URL}/api/portal/batches", json=batch_data)
        assert create_resp.status_code == 200
        batch_id = create_resp.json()["id"]
        self.created_batch_ids.append(batch_id)
        
        # Create a student in this batch
        student_data = {
            "full_name": f"TEST_Student_{uuid.uuid4().hex[:6]}",
            "age_group": "5-10",
            "batch_id": batch_id,
            "chess_level": "Beginner",
            "status": "Active"
        }
        student_resp = self.session.post(f"{BASE_URL}/api/portal/students", json=student_data)
        assert student_resp.status_code == 200
        student_id = student_resp.json()["id"]
        
        # Try to delete batch - should fail
        delete_resp = self.session.delete(f"{BASE_URL}/api/portal/batches/{batch_id}")
        assert delete_resp.status_code == 400, f"Expected 400, got {delete_resp.status_code}"
        assert "students" in delete_resp.json().get("detail", "").lower()
        
        # Cleanup student
        self.session.delete(f"{BASE_URL}/api/portal/students/{student_id}")
        
        print(f"✓ Delete batch with students correctly fails with 400")


class TestPortalHolidays:
    """Test batch holiday management"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and create test batch"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200
        
        # Create test batch
        batch_data = {"name": f"TEST_Holiday_{uuid.uuid4().hex[:6]}", "max_capacity": 10}
        create_resp = self.session.post(f"{BASE_URL}/api/portal/batches", json=batch_data)
        assert create_resp.status_code == 200
        self.batch_id = create_resp.json()["id"]
    
    def teardown_method(self):
        """Cleanup test batch"""
        try:
            self.session.delete(f"{BASE_URL}/api/portal/batches/{self.batch_id}")
        except Exception:
            pass
    
    def test_add_holiday(self):
        """POST /api/portal/batches/:id/holidays - add holiday"""
        holiday_data = {"date": "2026-01-26", "reason": "Republic Day"}
        
        response = self.session.post(
            f"{BASE_URL}/api/portal/batches/{self.batch_id}/holidays",
            json=holiday_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify holiday added
        list_resp = self.session.get(f"{BASE_URL}/api/portal/batches")
        batch = next((b for b in list_resp.json() if b["id"] == self.batch_id), None)
        assert batch is not None
        assert len(batch["holidays"]) == 1
        assert batch["holidays"][0]["date"] == "2026-01-26"
        assert batch["holidays"][0]["reason"] == "Republic Day"
        
        print(f"✓ Added holiday: {holiday_data['date']} - {holiday_data['reason']}")
    
    def test_remove_holiday(self):
        """DELETE /api/portal/batches/:id/holidays - remove holiday"""
        # Add a holiday first
        holiday_data = {"date": "2026-08-15", "reason": "Independence Day"}
        self.session.post(f"{BASE_URL}/api/portal/batches/{self.batch_id}/holidays", json=holiday_data)
        
        # Remove the holiday
        response = self.session.delete(
            f"{BASE_URL}/api/portal/batches/{self.batch_id}/holidays?date=2026-08-15"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify holiday removed
        list_resp = self.session.get(f"{BASE_URL}/api/portal/batches")
        batch = next((b for b in list_resp.json() if b["id"] == self.batch_id), None)
        assert batch is not None
        assert len(batch["holidays"]) == 0
        
        print(f"✓ Removed holiday successfully")


class TestPortalStudents:
    """Test student CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200
        self.created_student_ids = []
        
        # Get first batch for testing
        batches_resp = self.session.get(f"{BASE_URL}/api/portal/batches")
        batches = batches_resp.json()
        self.test_batch_id = batches[0]["id"] if batches else ""
    
    def teardown_method(self):
        """Cleanup created students"""
        for student_id in self.created_student_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/portal/students/{student_id}")
            except Exception:
                pass
    
    def test_list_students(self):
        """GET /api/portal/students - list all students"""
        response = self.session.get(f"{BASE_URL}/api/portal/students")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of students"
        print(f"✓ Listed {len(data)} students")
    
    def test_create_student_with_all_fields(self):
        """POST /api/portal/students - create student with all fields"""
        student_data = {
            "full_name": f"TEST_Student_{uuid.uuid4().hex[:6]}",
            "age_group": "10-15",
            "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "9876543210",
            "country_code": "+91",
            "parent_name": "Test Parent",
            "batch_id": self.test_batch_id,
            "joining_date": "2026-01-15",
            "chess_level": "Intermediate",
            "fee_per_block": 2500.0,
            "status": "Active",
            "date_of_birth": "2015-05-20"
        }
        
        response = self.session.post(f"{BASE_URL}/api/portal/students", json=student_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["full_name"] == student_data["full_name"]
        assert data["age_group"] == student_data["age_group"]
        assert data["email"] == student_data["email"]
        assert data["phone"] == student_data["phone"]
        assert data["country_code"] == student_data["country_code"]
        assert data["parent_name"] == student_data["parent_name"]
        assert data["batch_id"] == student_data["batch_id"]
        assert data["chess_level"] == student_data["chess_level"]
        assert data["fee_per_block"] == student_data["fee_per_block"]
        assert data["status"] == student_data["status"]
        assert data["date_of_birth"] == student_data["date_of_birth"]
        assert "id" in data
        
        self.created_student_ids.append(data["id"])
        print(f"✓ Created student: {data['full_name']} (id: {data['id']})")
    
    def test_update_student(self):
        """PUT /api/portal/students/:id - update student"""
        # Create a student
        student_data = {
            "full_name": f"TEST_Update_{uuid.uuid4().hex[:6]}",
            "age_group": "5-10",
            "chess_level": "Beginner",
            "status": "Active"
        }
        create_resp = self.session.post(f"{BASE_URL}/api/portal/students", json=student_data)
        assert create_resp.status_code == 200
        student_id = create_resp.json()["id"]
        self.created_student_ids.append(student_id)
        
        # Update the student
        update_data = {
            "chess_level": "Intermediate",
            "fee_per_block": 3000.0
        }
        update_resp = self.session.put(f"{BASE_URL}/api/portal/students/{student_id}", json=update_data)
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        
        # Verify update via GET
        get_resp = self.session.get(f"{BASE_URL}/api/portal/students/{student_id}")
        assert get_resp.status_code == 200
        updated = get_resp.json()
        assert updated["chess_level"] == "Intermediate"
        assert updated["fee_per_block"] == 3000.0
        
        print(f"✓ Updated student: chess_level={updated['chess_level']}, fee={updated['fee_per_block']}")
    
    def test_delete_student(self):
        """DELETE /api/portal/students/:id - delete student"""
        # Create a student
        student_data = {
            "full_name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
            "age_group": "5-10",
            "chess_level": "Beginner"
        }
        create_resp = self.session.post(f"{BASE_URL}/api/portal/students", json=student_data)
        assert create_resp.status_code == 200
        student_id = create_resp.json()["id"]
        
        # Delete the student
        delete_resp = self.session.delete(f"{BASE_URL}/api/portal/students/{student_id}")
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}"
        
        # Verify deletion
        get_resp = self.session.get(f"{BASE_URL}/api/portal/students/{student_id}")
        assert get_resp.status_code == 404, "Student should be deleted"
        
        print(f"✓ Deleted student successfully")
    
    def test_filter_students_by_batch(self):
        """GET /api/portal/students?batch_id=... - filter by batch"""
        if not self.test_batch_id:
            pytest.skip("No batch available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/portal/students?batch_id={self.test_batch_id}")
        assert response.status_code == 200
        
        data = response.json()
        # All returned students should be in the specified batch
        for student in data:
            assert student["batch_id"] == self.test_batch_id or student["batch_id"] == ""
        
        print(f"✓ Filtered students by batch: {len(data)} results")
    
    def test_filter_students_by_status(self):
        """GET /api/portal/students?status=Active - filter by status"""
        response = self.session.get(f"{BASE_URL}/api/portal/students?status=Active")
        assert response.status_code == 200
        
        data = response.json()
        for student in data:
            assert student["status"] == "Active"
        
        print(f"✓ Filtered students by status: {len(data)} active students")
    
    def test_filter_students_by_chess_level(self):
        """GET /api/portal/students?chess_level=Beginner - filter by level"""
        response = self.session.get(f"{BASE_URL}/api/portal/students?chess_level=Beginner")
        assert response.status_code == 200
        
        data = response.json()
        for student in data:
            assert student["chess_level"] == "Beginner"
        
        print(f"✓ Filtered students by chess level: {len(data)} beginners")
    
    def test_search_students(self):
        """GET /api/portal/students?search=... - search students"""
        # Create a student with unique name
        unique_name = f"TEST_SearchUnique_{uuid.uuid4().hex[:8]}"
        student_data = {
            "full_name": unique_name,
            "age_group": "5-10",
            "chess_level": "Beginner"
        }
        create_resp = self.session.post(f"{BASE_URL}/api/portal/students", json=student_data)
        assert create_resp.status_code == 200
        student_id = create_resp.json()["id"]
        self.created_student_ids.append(student_id)
        
        # Search for the student
        response = self.session.get(f"{BASE_URL}/api/portal/students?search={unique_name[:15]}")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) >= 1, "Should find at least one student"
        assert any(s["full_name"] == unique_name for s in data)
        
        print(f"✓ Search found student: {unique_name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
