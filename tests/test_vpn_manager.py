import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vpn_manager import VPNManager
import constants as C


class TestVPNManager:
    """Test suite for VPNManager class."""
    
    @pytest.fixture
    def vpn_manager(self):
        """Create a VPNManager instance for testing."""
        manager = VPNManager()
        return manager
    
    def test_initial_state(self, vpn_manager):
        """Test that VPNManager starts in correct initial state."""
        assert vpn_manager._state == C.VpnState.NO_CONFIG_SELECTED
        assert vpn_manager._process is None
        assert vpn_manager._current_config_path is None
    
    @patch('vpn_manager.subprocess.Popen')
    @patch('vpn_manager.C.LOG_FILE_PATH')
    @patch('vpn_manager.C.HELPER_SCRIPT_PATH')
    def test_connect_success(self, mock_helper_path, mock_log_path, mock_popen, vpn_manager):
        """Test successful VPN connection."""
        # Setup mocks
        mock_helper_path.__str__.return_value = '/usr/local/bin/helper.sh'
        mock_log_path.exists.return_value = False
        mock_log_path.__str__.return_value = '/tmp/test.log'
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ('', '')
        mock_popen.return_value = mock_process
        
        # Test connection
        vpn_manager.connect('/tmp/test.ovpn', 'testuser', 'testpass')
        
        assert vpn_manager._state == C.VpnState.CONNECTING
        mock_popen.assert_called_once()
    
    @patch('vpn_manager.subprocess.Popen')
    @patch('vpn_manager.C.LOG_FILE_PATH')
    def test_connect_auth_failure(self, mock_log_path, mock_popen, vpn_manager):
        """Test VPN connection with authentication failure."""
        mock_log_path.exists.return_value = False
        
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ('', 'Authentication failed')
        mock_popen.return_value = mock_process
        
        vpn_manager.connect('/tmp/test.ovpn', 'wronguser', 'wrongpass')
        
        # Should cleanup on error
        assert vpn_manager._process is None
    
    def test_connect_when_already_connected(self, vpn_manager):
        """Test that connecting when already connected does nothing."""
        vpn_manager._state = C.VpnState.CONNECTED
        
        vpn_manager.connect('/tmp/test.ovpn', 'user', 'pass')
        
        # State should remain CONNECTED
        assert vpn_manager._state == C.VpnState.CONNECTED
    
    @patch('vpn_manager.subprocess.run')
    def test_disconnect(self, mock_run, vpn_manager):
        """Test VPN disconnection."""
        vpn_manager._current_config_path = Path('/tmp/test.ovpn')
        vpn_manager._state = C.VpnState.CONNECTED
        
        mock_run.return_value = MagicMock(stdout='Disconnected', stderr='')
        
        vpn_manager.disconnect()
        
        # After disconnect, manager should transition to DISCONNECTED
        assert vpn_manager._state == C.VpnState.DISCONNECTED
        mock_run.assert_called_once()
    
    def test_disconnect_when_not_connected(self, vpn_manager):
        """Test disconnecting when not connected."""
        vpn_manager._current_config_path = None
        
        vpn_manager.disconnect()
        
        # Should emit log message about not being connected
    
    @patch('vpn_manager.subprocess.run')
    @patch('vpn_manager.C.LOG_FILE_PATH')
    def test_check_connection_status_connected(self, mock_log_path, mock_run, vpn_manager):
        """Test checking connection status when connected."""
        vpn_manager._current_config_path = Path('/tmp/test.ovpn')
        vpn_manager._state = C.VpnState.CONNECTING
        
        mock_run.return_value = MagicMock(
            stdout='connected',
            stderr='',
            returncode=0
        )
        mock_log_path.read_text.return_value = 'Initialization Sequence Completed'
        
        vpn_manager.check_connection_status()
        
        assert vpn_manager._state == C.VpnState.CONNECTED
    
    @patch('vpn_manager.subprocess.run')
    @patch('vpn_manager.C.LOG_FILE_PATH')
    def test_check_connection_status_auth_failed(self, mock_log_path, mock_run, vpn_manager):
        """Test checking connection status with auth failure."""
        vpn_manager._current_config_path = Path('/tmp/test.ovpn')
        vpn_manager._state = C.VpnState.CONNECTING
        
        mock_run.return_value = MagicMock(
            stdout='error',
            stderr='',
            returncode=0
        )
        mock_log_path.read_text.return_value = 'AUTH_FAILED'
        
        vpn_manager.check_connection_status()
        
        assert vpn_manager._state == C.VpnState.AUTH_FAILED
    
    def test_cleanup_on_error(self, vpn_manager):
        """Test cleanup sets correct error state."""
        vpn_manager._state = C.VpnState.CONNECTING
        vpn_manager._current_config_path = Path('/tmp/test.ovpn')
        
        vpn_manager._cleanup(error=True)
        
        assert vpn_manager._state == C.VpnState.ERROR
        assert vpn_manager._current_config_path is None
        assert vpn_manager._process is None
    
    def test_cleanup_on_disconnect(self, vpn_manager):
        """Test cleanup after normal disconnect."""
        vpn_manager._state = C.VpnState.DISCONNECTING
        vpn_manager._current_config_path = Path('/tmp/test.ovpn')
        
        vpn_manager._cleanup(error=False)
        
        assert vpn_manager._state == C.VpnState.DISCONNECTED
        assert vpn_manager._current_config_path is None
