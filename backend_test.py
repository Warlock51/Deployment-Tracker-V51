
import requests
import unittest
import json
import sys
from datetime import datetime

class DeploymentTrackerAPITester(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(DeploymentTrackerAPITester, self).__init__(*args, **kwargs)
        self.base_url = "https://7cab5d6d-e62a-4851-a04b-559a2171917a.preview.emergentagent.com/api"
        self.admin_token = None
        self.dev_token = None
        self.admin_user_id = None
        self.dev_user_id = None
        self.test_bug_id = None
        self.test_fix_id = None
        self.test_idea_id = None
        self.test_deployment_id = None

    def setUp(self):
        # Login as admin
        admin_login_response = self.login("testadmin", "admin123")
        self.admin_token = admin_login_response.get("access_token")
        self.admin_user_id = admin_login_response.get("user", {}).get("id")
        
        # Create and login as developer
        try:
            dev_register_response = self.register("testdev", "testdev@example.com", "dev123", "developer")
            self.dev_token = dev_register_response.get("access_token")
            self.dev_user_id = dev_register_response.get("user", {}).get("id")
        except Exception as e:
            # If registration fails (user might already exist), try login
            dev_login_response = self.login("testdev", "dev123")
            self.dev_token = dev_login_response.get("access_token")
            self.dev_user_id = dev_login_response.get("user", {}).get("id")

    def login(self, username, password):
        """Login and get token"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200, f"Login failed: {response.text}")
        return response.json()

    def register(self, username, email, password, role="developer"):
        """Register a new user"""
        response = requests.post(
            f"{self.base_url}/auth/register",
            json={"username": username, "email": email, "password": password, "role": role}
        )
        self.assertEqual(response.status_code, 200, f"Registration failed: {response.text}")
        return response.json()

    def test_01_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔍 Testing Authentication Endpoints...")
        
        # Test admin login
        admin_response = self.login("testadmin", "admin123")
        self.assertIn("access_token", admin_response)
        self.assertEqual(admin_response["user"]["role"], "admin")
        print("✅ Admin login successful")
        
        # Test developer login
        dev_response = self.login("testdev", "dev123")
        self.assertIn("access_token", dev_response)
        self.assertEqual(dev_response["user"]["role"], "developer")
        print("✅ Developer login successful")
        
        # Test me endpoint with admin token
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        me_response = requests.get(f"{self.base_url}/auth/me", headers=headers)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["role"], "admin")
        print("✅ Auth/me endpoint working correctly")

    def test_02_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        print("\n🔍 Testing Dashboard Stats Endpoint...")
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        response = requests.get(f"{self.base_url}/dashboard", headers=headers)
        self.assertEqual(response.status_code, 200)
        
        stats = response.json()
        self.assertIn("total_bugs", stats)
        self.assertIn("open_bugs", stats)
        self.assertIn("pending_fixes", stats)
        self.assertIn("recent_deployments", stats)
        self.assertIn("new_ideas", stats)
        self.assertIn("total_users", stats)
        
        print("✅ Dashboard stats endpoint working correctly")

    def test_03_bugs_crud(self):
        """Test bug CRUD operations"""
        print("\n🔍 Testing Bug CRUD Operations...")
        
        # Create a bug as developer
        headers = {"Authorization": f"Bearer {self.dev_token}"}
        bug_data = {
            "title": "Test Bug",
            "description": "This is a test bug",
            "priority": "high"
        }
        
        create_response = requests.post(
            f"{self.base_url}/bugs",
            json=bug_data,
            headers=headers
        )
        self.assertEqual(create_response.status_code, 200)
        bug = create_response.json()
        self.test_bug_id = bug["id"]
        print(f"✅ Bug created with ID: {self.test_bug_id}")
        
        # Get all bugs
        get_all_response = requests.get(f"{self.base_url}/bugs", headers=headers)
        self.assertEqual(get_all_response.status_code, 200)
        bugs = get_all_response.json()
        self.assertIsInstance(bugs, list)
        print(f"✅ Retrieved {len(bugs)} bugs")
        
        # Get specific bug
        get_response = requests.get(f"{self.base_url}/bugs/{self.test_bug_id}", headers=headers)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["id"], self.test_bug_id)
        print("✅ Retrieved specific bug")
        
        # Update bug
        update_data = {"status": "in_progress"}
        update_response = requests.put(
            f"{self.base_url}/bugs/{self.test_bug_id}",
            json=update_data,
            headers=headers
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["status"], "in_progress")
        print("✅ Updated bug status")

    def test_04_fixes_crud(self):
        """Test fix CRUD operations"""
        print("\n🔍 Testing Fix CRUD Operations...")
        
        # Create a fix as developer
        headers = {"Authorization": f"Bearer {self.dev_token}"}
        fix_data = {
            "title": "Test Fix",
            "description": "This is a test fix",
            "related_bug_id": self.test_bug_id
        }
        
        create_response = requests.post(
            f"{self.base_url}/fixes",
            json=fix_data,
            headers=headers
        )
        self.assertEqual(create_response.status_code, 200)
        fix = create_response.json()
        self.test_fix_id = fix["id"]
        print(f"✅ Fix created with ID: {self.test_fix_id}")
        
        # Get all fixes
        get_all_response = requests.get(f"{self.base_url}/fixes", headers=headers)
        self.assertEqual(get_all_response.status_code, 200)
        fixes = get_all_response.json()
        self.assertIsInstance(fixes, list)
        print(f"✅ Retrieved {len(fixes)} fixes")
        
        # Update fix
        update_data = {"status": "deployed"}
        update_response = requests.put(
            f"{self.base_url}/fixes/{self.test_fix_id}",
            json=update_data,
            headers=headers
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["status"], "deployed")
        print("✅ Updated fix status")

    def test_05_deployments_crud(self):
        """Test deployment CRUD operations"""
        print("\n🔍 Testing Deployment CRUD Operations...")
        
        # Create a deployment as developer
        headers = {"Authorization": f"Bearer {self.dev_token}"}
        deployment_data = {
            "version": "1.0.0",
            "description": "Test deployment",
            "environment": "dev",
            "changes_included": ["Fix for bug #123", "New feature X"]
        }
        
        create_response = requests.post(
            f"{self.base_url}/deployments",
            json=deployment_data,
            headers=headers
        )
        self.assertEqual(create_response.status_code, 200)
        deployment = create_response.json()
        self.test_deployment_id = deployment["id"]
        print(f"✅ Deployment created with ID: {self.test_deployment_id}")
        
        # Get all deployments
        get_all_response = requests.get(f"{self.base_url}/deployments", headers=headers)
        self.assertEqual(get_all_response.status_code, 200)
        deployments = get_all_response.json()
        self.assertIsInstance(deployments, list)
        print(f"✅ Retrieved {len(deployments)} deployments")

    def test_06_ideas_crud(self):
        """Test idea CRUD operations"""
        print("\n🔍 Testing Idea CRUD Operations...")
        
        # Create an idea as developer
        headers = {"Authorization": f"Bearer {self.dev_token}"}
        idea_data = {
            "title": "Test Idea",
            "description": "This is a test idea",
            "priority": "medium"
        }
        
        create_response = requests.post(
            f"{self.base_url}/ideas",
            json=idea_data,
            headers=headers
        )
        self.assertEqual(create_response.status_code, 200)
        idea = create_response.json()
        self.test_idea_id = idea["id"]
        print(f"✅ Idea created with ID: {self.test_idea_id}")
        
        # Get all ideas
        get_all_response = requests.get(f"{self.base_url}/ideas", headers=headers)
        self.assertEqual(get_all_response.status_code, 200)
        ideas = get_all_response.json()
        self.assertIsInstance(ideas, list)
        print(f"✅ Retrieved {len(ideas)} ideas")
        
        # Update idea
        update_data = {"status": "under_review"}
        update_response = requests.put(
            f"{self.base_url}/ideas/{self.test_idea_id}",
            json=update_data,
            headers=headers
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["status"], "under_review")
        print("✅ Updated idea status")

    def test_07_user_management(self):
        """Test user management (admin only)"""
        print("\n🔍 Testing User Management (Admin Only)...")
        
        # Get all users as admin
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        get_users_response = requests.get(f"{self.base_url}/users", headers=admin_headers)
        self.assertEqual(get_users_response.status_code, 200)
        users = get_users_response.json()
        self.assertIsInstance(users, list)
        print(f"✅ Admin can retrieve users list ({len(users)} users)")
        
        # Try to get users as developer (should work but with limited permissions)
        dev_headers = {"Authorization": f"Bearer {self.dev_token}"}
        get_users_dev_response = requests.get(f"{self.base_url}/users", headers=dev_headers)
        self.assertEqual(get_users_dev_response.status_code, 200)
        print("✅ Developer can access users list")
        
        # Try to delete a user as developer (should fail)
        if len(users) > 2:  # Make sure we have at least one user to delete besides admin and dev
            user_to_delete = next((u for u in users if u["id"] != self.admin_user_id and u["id"] != self.dev_user_id), None)
            if user_to_delete:
                delete_response = requests.delete(
                    f"{self.base_url}/users/{user_to_delete['id']}",
                    headers=dev_headers
                )
                self.assertNotEqual(delete_response.status_code, 200)
                print("✅ Developer cannot delete users (permission denied)")

    def test_08_permission_checks(self):
        """Test permission checks for editing resources"""
        print("\n🔍 Testing Permission Checks...")
        
        # Create a bug as admin
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        admin_bug_data = {
            "title": "Admin Bug",
            "description": "This is a bug created by admin",
            "priority": "medium"
        }
        
        admin_bug_response = requests.post(
            f"{self.base_url}/bugs",
            json=admin_bug_data,
            headers=admin_headers
        )
        self.assertEqual(admin_bug_response.status_code, 200)
        admin_bug_id = admin_bug_response.json()["id"]
        print(f"✅ Admin created bug with ID: {admin_bug_id}")
        
        # Try to update admin's bug as developer
        dev_headers = {"Authorization": f"Bearer {self.dev_token}"}
        update_data = {"status": "resolved"}
        
        # Admin should be able to update developer's bug
        admin_update_response = requests.put(
            f"{self.base_url}/bugs/{self.test_bug_id}",
            json=update_data,
            headers=admin_headers
        )
        self.assertEqual(admin_update_response.status_code, 200)
        print("✅ Admin can update developer's bug")
        
        # Developer should be able to update their own bug
        dev_update_response = requests.put(
            f"{self.base_url}/bugs/{self.test_bug_id}",
            json={"status": "in_progress"},
            headers=dev_headers
        )
        self.assertEqual(dev_update_response.status_code, 200)
        print("✅ Developer can update their own bug")
        
        # Developer should be able to update admin's bug if they have permission
        # This might fail if the backend properly checks permissions
        dev_update_admin_response = requests.put(
            f"{self.base_url}/bugs/{admin_bug_id}",
            json=update_data,
            headers=dev_headers
        )
        
        if dev_update_admin_response.status_code == 200:
            print("⚠️ Developer can update admin's bug (possible permission issue)")
        else:
            print("✅ Developer cannot update admin's bug (permission check working)")

def run_tests():
    suite = unittest.TestSuite()
    suite.addTest(DeploymentTrackerAPITester('test_01_auth_endpoints'))
    suite.addTest(DeploymentTrackerAPITester('test_02_dashboard_stats'))
    suite.addTest(DeploymentTrackerAPITester('test_03_bugs_crud'))
    suite.addTest(DeploymentTrackerAPITester('test_04_fixes_crud'))
    suite.addTest(DeploymentTrackerAPITester('test_05_deployments_crud'))
    suite.addTest(DeploymentTrackerAPITester('test_06_ideas_crud'))
    suite.addTest(DeploymentTrackerAPITester('test_07_user_management'))
    suite.addTest(DeploymentTrackerAPITester('test_08_permission_checks'))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n📊 Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    return len(result.failures) + len(result.errors)

if __name__ == "__main__":
    sys.exit(run_tests())
