#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class ChessZenAPITester:
    def __init__(self, base_url="https://chesszen-academy.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if headers:
            test_headers.update(headers)
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                if files:
                    # Remove Content-Type for multipart/form-data
                    test_headers.pop('Content-Type', None)
                    response = self.session.post(url, data=data, files=files, headers=test_headers, timeout=30)
                elif headers and headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                    # Use form data
                    test_headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    response = self.session.post(url, data=data, headers=test_headers, timeout=30)
                else:
                    response = self.session.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PATCH':
                response = self.session.patch(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@chesszen.com", "password": "ChessZen@Admin2024"}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            print(f"   ✅ Token received: {self.token[:20]}...")
            return True
        return False

    def test_get_me(self):
        """Test get current user"""
        return self.run_test("Get Current User", "GET", "auth/me", 200)

    def test_create_enquiry(self):
        """Test creating an enquiry"""
        enquiry_data = {
            "parent_name": "Test Parent",
            "student_age": 12,
            "phone": "+91-9876543210",
            "email": "test@example.com",
            "preferred_batch": "Weekend Morning",
            "skill_level": "Beginner",
            "demo_interest": True,
            "message": "Test enquiry message",
            "consent": True
        }
        success, response = self.run_test(
            "Create Enquiry",
            "POST",
            "enquiries",
            200,
            data=enquiry_data
        )
        return response.get('id') if success else None

    def test_get_enquiries(self):
        """Test getting enquiries (admin only)"""
        return self.run_test("Get Enquiries", "GET", "enquiries", 200)

    def test_create_testimonial(self):
        """Test creating a testimonial"""
        testimonial_data = {
            "name": "Test Parent",
            "testimonial": "Great chess coaching! My child loves the classes.",
            "rating": "5",
            "relation": "Parent"
        }
        # Use form data for testimonial endpoint
        success, response = self.run_test(
            "Create Testimonial",
            "POST",
            "testimonials",
            200,
            data=testimonial_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        return response.get('id') if success else None

    def test_get_public_testimonials(self):
        """Test getting public testimonials"""
        return self.run_test("Get Public Testimonials", "GET", "testimonials?approved_only=true", 200)

    def test_get_admin_testimonials(self):
        """Test getting all testimonials (admin only)"""
        return self.run_test("Get Admin Testimonials", "GET", "admin/testimonials", 200)

    def test_approve_testimonial(self, testimonial_id):
        """Test approving a testimonial"""
        if not testimonial_id:
            print("⚠️  Skipping testimonial approval - no testimonial ID")
            return False
        
        return self.run_test(
            "Approve Testimonial",
            "PATCH",
            f"admin/testimonials/{testimonial_id}",
            200,
            data={"approved": True}
        )

    def test_create_booking(self):
        """Test creating a demo class booking"""
        booking_data = {
            "parent_name": "Test Parent",
            "student_name": "Test Student",
            "student_age": 10,
            "phone": "+91-9876543210",
            "email": "test@example.com",
            "preferred_date": "2025-01-15",
            "preferred_time": "10:00 AM",
            "skill_level": "Beginner",
            "message": "Test booking message"
        }
        success, response = self.run_test(
            "Create Booking",
            "POST",
            "bookings",
            200,
            data=booking_data
        )
        return response.get('id') if success else None

    def test_get_bookings(self):
        """Test getting bookings (admin only)"""
        return self.run_test("Get Bookings", "GET", "bookings", 200)

    def test_get_available_slots(self):
        """Test getting available slots for a date"""
        test_date = "2025-01-15"
        return self.run_test(
            "Get Available Slots",
            "GET",
            f"available-slots?date={test_date}",
            200
        )

    def test_update_booking_status(self, booking_id):
        """Test updating booking status"""
        if not booking_id:
            print("⚠️  Skipping booking status update - no booking ID")
            return False
        
        return self.run_test(
            "Update Booking Status",
            "PATCH",
            f"bookings/{booking_id}/status?status=confirmed",
            200
        )

    def test_logout(self):
        """Test logout"""
        return self.run_test("Logout", "POST", "auth/logout", 200)

def main():
    print("🚀 Starting ChessZen API Tests")
    print("=" * 50)
    
    tester = ChessZenAPITester()
    
    # Test basic API
    tester.test_root_endpoint()
    
    # Test authentication
    if not tester.test_admin_login():
        print("❌ Admin login failed, stopping authenticated tests")
        print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
        return 1
    
    # Test authenticated endpoints
    tester.test_get_me()
    
    # Test enquiry functionality
    enquiry_id = tester.test_create_enquiry()
    tester.test_get_enquiries()
    
    # Test testimonial functionality
    testimonial_id = tester.test_create_testimonial()
    tester.test_get_public_testimonials()
    tester.test_get_admin_testimonials()
    tester.test_approve_testimonial(testimonial_id)
    
    # Test booking functionality
    booking_id = tester.test_create_booking()
    tester.test_get_bookings()
    tester.test_get_available_slots()
    tester.test_update_booking_status(booking_id)
    
    # Test logout
    tester.test_logout()
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())