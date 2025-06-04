import unittest
import json
from datetime import datetime, date, time, timedelta
from app import app, db, User, Shift, TimeEntry, VacationRequest, OvertimeEntry

class APISmokeTests(unittest.TestCase):
    test_user_id = None  # Class attribute to store the main test user's ID
    logged_in_user_data = None # Store login response

    @classmethod
    def setUpClass(cls):
        cls.app_context = app.app_context()
        cls.app_context.push()
        cls.client = app.test_client()

        # Clean up potential existing main test user
        existing_user = User.query.filter_by(username='testuser_main').first()
        if existing_user:
            Shift.query.filter_by(user_id=existing_user.id).delete()
            TimeEntry.query.filter_by(user_id=existing_user.id).delete()
            VacationRequest.query.filter_by(user_id=existing_user.id).delete()
            OvertimeEntry.query.filter_by(user_id=existing_user.id).delete()
            db.session.delete(existing_user)
            db.session.commit()

        # Register the main test user
        response = cls.client.post('/register',
                                 data=json.dumps({'username': 'testuser_main', 'email': 'main@example.com', 'password': 'password_main'}),
                                 content_type='application/json')
        if response.status_code != 201:
            raise Exception(f"Failed to register main test user in setUpClass: {response.data.decode()} (Status: {response.status_code})")

        user = User.query.filter_by(username='testuser_main').first()
        if not user:
            raise Exception("Main test user 'testuser_main' not found in DB after registration in setUpClass.")
        APISmokeTests.test_user_id = user.id

    @classmethod
    def tearDownClass(cls):
        # Clean up the main test user
        if APISmokeTests.test_user_id:
            user = User.query.get(APISmokeTests.test_user_id)
            if user:
                Shift.query.filter_by(user_id=user.id).delete()
                TimeEntry.query.filter_by(user_id=user.id).delete()
                VacationRequest.query.filter_by(user_id=user.id).delete()
                OvertimeEntry.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()
        cls.app_context.pop()

    def setUp(self):
        self.app = APISmokeTests.client # Use client from setUpClass
        self.assertIsNotNone(APISmokeTests.test_user_id, "User ID for 'testuser_main' was not set in setUpClass.")

    # test_01_register_user now tests a *secondary* registration and conflict
    def test_01_register_user_secondary_and_conflict(self):
        print("\nRunning test_01_register_user_secondary_and_conflict...")
        # Test successful registration of a new, unique user
        unique_username = f"testuser_unique_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        response = self.app.post('/register',
                                 data=json.dumps({'username': unique_username, 'email': f'{unique_username}@example.com', 'password': 'password123'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201, f"Failed to register unique user: {response.data.decode()}")
        data = json.loads(response.data)
        self.assertEqual(data['message'], 'User created successfully')

        # Test registration conflict for the main user (already registered in setUpClass)
        response_conflict = self.app.post('/register',
                                 data=json.dumps({'username': 'testuser_main', 'email': 'main_conflict@example.com', 'password': 'password_main'}),
                                 content_type='application/json')
        self.assertEqual(response_conflict.status_code, 409, f"Conflict test failed: {response_conflict.data.decode()}")
        data_conflict = json.loads(response_conflict.data)
        self.assertEqual(data_conflict['message'], 'User already exists')


    def test_02_login_user(self):
        print("\nRunning test_02_login_user...")
        response = self.app.post('/login',
                                 data=json.dumps({'username': 'testuser_main', 'password': 'password_main'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200, f"Login failed: {response.data.decode()}")
        data = json.loads(response.data)
        self.assertEqual(data['message'], 'Login successful')
        self.assertEqual(data['username'], 'testuser_main')
        APISmokeTests.logged_in_user_data = data


    def test_03_create_and_get_shift(self):
        print("\nRunning test_03_create_and_get_shift...")
        shift_data = {
            'user_id': APISmokeTests.test_user_id,
            'date': '2024-08-15',
            'start_time': '09:00',
            'end_time': '17:00',
            'location': 'Test Office'
        }
        response = self.app.post('/shifts', data=json.dumps(shift_data), content_type='application/json')
        self.assertEqual(response.status_code, 201, f"Failed to create shift: {response.data.decode()}")
        created_shift_data = json.loads(response.data)['shift']

        response_get = self.app.get(f'/shifts?user_id={APISmokeTests.test_user_id}&year=2024&month=8')
        self.assertEqual(response_get.status_code, 200)
        shifts = json.loads(response_get.data)
        self.assertTrue(any(s['id'] == created_shift_data['id'] for s in shifts), "Created shift not found in GET response.")

    def test_04_time_entries(self):
        print("\nRunning test_04_time_entries...")
        # Clock In
        response_in = self.app.post('/time_entries/clock_in', data=json.dumps({'user_id': APISmokeTests.test_user_id}), content_type='application/json')
        self.assertEqual(response_in.status_code, 201, f"Clock-in failed: {response_in.data.decode()}")

        # Clock Out
        response_out = self.app.post('/time_entries/clock_out', data=json.dumps({'user_id': APISmokeTests.test_user_id}), content_type='application/json')
        self.assertEqual(response_out.status_code, 200, f"Clock-out failed: {response_out.data.decode()}")
        data_out = json.loads(response_out.data)['time_entry']
        self.assertIn('duration_hours', data_out)

        # Get Time Entries
        current_date_iso = date.today().isoformat()
        response_get = self.app.get(f'/time_entries?user_id={APISmokeTests.test_user_id}&start_date={current_date_iso}&end_date={current_date_iso}')
        self.assertEqual(response_get.status_code, 200)
        entries = json.loads(response_get.data)
        self.assertTrue(any(e['id'] == data_out['id'] for e in entries), "Clocked entry not found in GET response.")

    def test_05_vacation_request(self):
        print("\nRunning test_05_vacation_request...")
        vac_data = {
            'user_id': APISmokeTests.test_user_id,
            'start_date': '2024-12-20',
            'end_date': '2024-12-22',
            'reason': 'Holiday break'
        }
        response = self.app.post('/vacation_requests', data=json.dumps(vac_data), content_type='application/json')
        self.assertEqual(response.status_code, 201, f"Failed to create vacation request: {response.data.decode()}")
        created_vac_data = json.loads(response.data)['request']

        response_get = self.app.get(f'/vacation_requests?user_id={APISmokeTests.test_user_id}&status=pending')
        self.assertEqual(response_get.status_code, 200)
        requests = json.loads(response_get.data)
        self.assertTrue(any(r['id'] == created_vac_data['id'] for r in requests), "Created vacation request not found.")

    def test_06_overtime_entry(self):
        print("\nRunning test_06_overtime_entry...")
        ot_data = {
            'user_id': APISmokeTests.test_user_id,
            'date': '2024-08-16',
            'hours': 2.5,
            'overtime_type': 'Late work',
            'notes': 'Project deadline'
        }
        response = self.app.post('/overtime_entries', data=json.dumps(ot_data), content_type='application/json')
        self.assertEqual(response.status_code, 201, f"Failed to create overtime entry: {response.data.decode()}")
        created_ot_data = json.loads(response.data)['entry']

        response_get = self.app.get(f'/overtime_entries?user_id={APISmokeTests.test_user_id}&status=pending')
        self.assertEqual(response_get.status_code, 200)
        entries = json.loads(response_get.data)
        self.assertTrue(any(e['id'] == created_ot_data['id'] for e in entries), "Created overtime entry not found.")

    def test_07_annual_report(self):
        print("\nRunning test_07_annual_report...")
        report_year = date.today().year
        response = self.app.get(f'/reports/annual_hours/{APISmokeTests.test_user_id}/{report_year}')
        self.assertEqual(response.status_code, 200, f"Failed to get annual report: {response.data.decode()}")
        report_data = json.loads(response.data)
        self.assertEqual(report_data['user_id'], APISmokeTests.test_user_id)
        self.assertEqual(report_data['year'], report_year)
        self.assertIn('total_annual_hours', report_data)
        self.assertIn('monthly_breakdown', report_data)
        self.assertEqual(len(report_data['monthly_breakdown']), 12)


if __name__ == '__main__':
    suite = unittest.TestSuite()
    # Add tests in desired order of execution
    suite.addTest(APISmokeTests('test_01_register_user_secondary_and_conflict'))
    suite.addTest(APISmokeTests('test_02_login_user'))
    suite.addTest(APISmokeTests('test_03_create_and_get_shift'))
    suite.addTest(APISmokeTests('test_04_time_entries'))
    suite.addTest(APISmokeTests('test_05_vacation_request'))
    suite.addTest(APISmokeTests('test_06_overtime_entry'))
    suite.addTest(APISmokeTests('test_07_annual_report'))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        exit(1)
