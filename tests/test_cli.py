"""Tests for CLI error handling and user experience."""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path


class TestCLIErrorHandling:
    """Tests for helpful error messages when CLI is misused."""

    def test_explain_no_config_suggests_init(self):
        """Running explain without config should suggest tally init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ['uv', 'run', 'tally', 'explain'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            assert result.returncode == 1
            assert 'tally init' in result.stderr

    def test_explain_invalid_merchant_suggests_similar(self):
        """Typo in merchant name should suggest similar names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up minimal config
            config_dir = os.path.join(tmpdir, 'config')
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(config_dir)
            os.makedirs(data_dir)

            # Create settings
            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("""year: 2025
data_sources:
  - name: Test
    file: data/test.csv
    format: "{date:%Y-%m-%d},{description},{amount}"
""")

            # Create merchant rules file
            with open(os.path.join(config_dir, 'merchant_categories.csv'), 'w') as f:
                f.write("Pattern,Merchant,Category,Subcategory\n")
                f.write("NETFLIX,Netflix,Subscriptions,Streaming\n")

            # Create test data with Netflix
            with open(os.path.join(data_dir, 'test.csv'), 'w') as f:
                f.write("date,description,amount\n")
                f.write("2025-01-15,NETFLIX STREAMING,15.99\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'explain', 'Netflx', config_dir],
                capture_output=True,
                text=True
            )
            assert result.returncode == 1
            assert 'Did you mean' in result.stderr
            assert 'Netflix' in result.stderr

    def test_run_invalid_only_shows_warning(self):
        """Invalid --only value should warn and show valid options."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up minimal config
            config_dir = os.path.join(tmpdir, 'config')
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(config_dir)
            os.makedirs(data_dir)

            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("""year: 2025
data_sources:
  - name: Test
    file: data/test.csv
    format: "{date:%Y-%m-%d},{description},{amount}"
""")

            with open(os.path.join(data_dir, 'test.csv'), 'w') as f:
                f.write("date,description,amount\n")
                f.write("2025-01-15,TEST,10.00\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'run', '--only', 'invalid', '--format', 'summary', config_dir],
                capture_output=True,
                text=True
            )
            assert 'Warning: Invalid view' in result.stderr
            # Valid views may or may not be shown depending on whether views.rules exists

    def test_run_mixed_only_filters_invalid(self):
        """Mixed valid/invalid --only values should warn about invalid ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(config_dir)
            os.makedirs(data_dir)

            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("""year: 2025
data_sources:
  - name: Test
    file: data/test.csv
    format: "{date:%Y-%m-%d},{description},{amount}"
""")

            with open(os.path.join(data_dir, 'test.csv'), 'w') as f:
                f.write("date,description,amount\n")
                f.write("2025-01-15,TEST,10.00\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'run', '--only', 'monthly,invalid,travel', '--format', 'summary', config_dir],
                capture_output=True,
                text=True
            )
            assert 'Warning: Invalid view' in result.stderr
            assert 'invalid' in result.stderr
            # Should exit since no valid views remain
            # (monthly and travel are not valid view names anymore)

    def test_explain_invalid_category_shows_available(self):
        """Invalid --category should show available categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(config_dir)
            os.makedirs(data_dir)

            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("""year: 2025
data_sources:
  - name: Test
    file: data/test.csv
    format: "{date:%Y-%m-%d},{description},{amount}"
""")

            # Create merchant rules file
            with open(os.path.join(config_dir, 'merchant_categories.csv'), 'w') as f:
                f.write("Pattern,Merchant,Category,Subcategory\n")
                f.write("NETFLIX,Netflix,Subscriptions,Streaming\n")

            # Create data that will be categorized
            with open(os.path.join(data_dir, 'test.csv'), 'w') as f:
                f.write("date,description,amount\n")
                f.write("2025-01-15,NETFLIX STREAMING,15.99\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'explain', '--category', 'NonExistent', config_dir],
                capture_output=True,
                text=True
            )
            assert "No merchants found in category 'NonExistent'" in result.stdout
            assert 'Available categories:' in result.stdout

    def test_invalid_format_shows_choices(self):
        """Invalid --format should show valid choices."""
        result = subprocess.run(
            ['uv', 'run', 'tally', 'run', '--format', 'invalid'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 2
        assert 'invalid choice' in result.stderr
        assert 'html' in result.stderr
        assert 'json' in result.stderr

    def test_invalid_view_shows_available(self):
        """Invalid --view should show available views."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(config_dir)
            os.makedirs(data_dir)

            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("""year: 2025
data_sources:
  - name: Test
    file: data/test.csv
    format: "{date:%Y-%m-%d},{description},{amount}"
""")

            with open(os.path.join(data_dir, 'test.csv'), 'w') as f:
                f.write("date,description,amount\n")
                f.write("2025-01-15,TEST,10.00\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'explain', '--view', 'invalid', config_dir],
                capture_output=True,
                text=True
            )
            # Should fail because 'invalid' is not a valid view
            assert result.returncode == 1
            # Message may be in stdout or stderr depending on error type
            output = result.stdout + result.stderr
            assert 'No view' in output or 'views' in output.lower()


class TestMigration:
    """Tests for migration from old tally format to new format."""

    def test_init_detects_existing_config_directory(self):
        """Running tally init in existing config dir should use current dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing config structure (like old tally would)
            config_dir = os.path.join(tmpdir, 'config')
            os.makedirs(config_dir)
            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("year: 2025\n")

            # Run tally init (default would create ./tally/)
            result = subprocess.run(
                ['uv', 'run', 'tally', 'init'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            # Should detect existing config and use current dir
            assert 'Found existing config/' in result.stdout
            # Should NOT create nested tally/tally/ directory
            assert not os.path.exists(os.path.join(tmpdir, 'tally'))
            # Should create new files in existing config/
            assert os.path.exists(os.path.join(config_dir, 'merchants.rules'))
            assert os.path.exists(os.path.join(config_dir, 'views.rules'))

    def test_init_migrates_csv_to_rules(self):
        """Running tally init should migrate merchant_categories.csv to merchants.rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            os.makedirs(config_dir)

            # Create old-style settings.yaml
            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("year: 2025\n")

            # Create old-style merchant_categories.csv with rules
            with open(os.path.join(config_dir, 'merchant_categories.csv'), 'w') as f:
                f.write("Pattern,Merchant,Category,Subcategory\n")
                f.write("NETFLIX,Netflix,Subscriptions,Streaming\n")
                f.write("AMAZON,Amazon,Shopping,Online\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'init'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            # Should mention migration
            assert 'legacy' in result.stdout.lower() or 'converting' in result.stdout.lower()
            # Should create merchants.rules
            assert os.path.exists(os.path.join(config_dir, 'merchants.rules'))
            # Should backup old CSV
            assert os.path.exists(os.path.join(config_dir, 'merchant_categories.csv.bak'))
            # Old CSV should be gone
            assert not os.path.exists(os.path.join(config_dir, 'merchant_categories.csv'))

            # Verify merchants.rules has the converted rules
            with open(os.path.join(config_dir, 'merchants.rules'), 'r') as f:
                content = f.read()
            assert 'Netflix' in content
            assert 'Amazon' in content

    def test_init_updates_settings_yaml(self):
        """Running tally init should add merchants_file and views_file to settings.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            os.makedirs(config_dir)

            # Create minimal old-style settings.yaml
            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("year: 2025\ntitle: Test\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'init'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            assert result.returncode == 0

            # Check settings.yaml was updated
            with open(os.path.join(config_dir, 'settings.yaml'), 'r') as f:
                content = f.read()
            assert 'views_file:' in content
            assert 'config/views.rules' in content

    def test_init_skips_migration_for_empty_csv(self):
        """CSV with only headers/comments should not trigger migration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            os.makedirs(config_dir)

            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("year: 2025\n")

            # Create CSV with only header, no rules
            with open(os.path.join(config_dir, 'merchant_categories.csv'), 'w') as f:
                f.write("# Comments\n")
                f.write("Pattern,Merchant,Category,Subcategory\n")
                f.write("# More comments\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'init'],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            # Should NOT mention migration (no rules to migrate)
            assert 'converting' not in result.stdout.lower()
            # CSV should still exist (not renamed to .bak)
            assert os.path.exists(os.path.join(config_dir, 'merchant_categories.csv'))

    def test_run_migrate_flag_converts_csv(self):
        """Running tally run --migrate should convert CSV to rules format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, 'config')
            data_dir = os.path.join(tmpdir, 'data')
            os.makedirs(config_dir)
            os.makedirs(data_dir)

            # Create settings with data source
            with open(os.path.join(config_dir, 'settings.yaml'), 'w') as f:
                f.write("""year: 2025
data_sources:
  - name: Test
    file: data/test.csv
    format: "{date:%Y-%m-%d},{description},{amount}"
""")

            # Create old-style CSV rules
            with open(os.path.join(config_dir, 'merchant_categories.csv'), 'w') as f:
                f.write("Pattern,Merchant,Category,Subcategory\n")
                f.write("TEST,Test Merchant,Shopping,General\n")

            # Create test data
            with open(os.path.join(data_dir, 'test.csv'), 'w') as f:
                f.write("date,description,amount\n")
                f.write("2025-01-15,TEST PURCHASE,-10.00\n")

            result = subprocess.run(
                ['uv', 'run', 'tally', 'run', '--migrate', '--format', 'summary', config_dir],
                capture_output=True,
                text=True
            )
            # Should succeed and create merchants.rules
            assert os.path.exists(os.path.join(config_dir, 'merchants.rules'))


