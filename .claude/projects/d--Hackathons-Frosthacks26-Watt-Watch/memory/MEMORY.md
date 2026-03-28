# Watt Watch - GPU & CUDA Setup

## Hardware
- **GPU**: NVIDIA GeForce RTX 2050 (4GB VRAM)
- **Driver Version**: 581.57
- **GPU Status**: ✅ Detected and working

## CUDA Status
- **PyTorch CUDA requirement**: cu130 (CUDA 13.0)
- **CUDA Toolkit installed**: 12.8
- **Current PyTorch status**: ✅ CUDA detected and working (forwards-compatible)
- **Action needed**: Upgrade CUDA Toolkit from 12.8 → 13.0+ for proper version matching

## Installation Steps
1. Download CUDA 13.0 Toolkit from: https://developer.nvidia.com/cuda-13-0-download-archive
2. Select: Windows → x86_64 → Windows 11 → exe (local)
3. Run installer, uninstall old CUDA 12.8 when prompted
4. Verify: `nvcc --version` and `python -c "import torch; print(torch.version.cuda)"`

## PyTorch Installation
- Current: torch==2.11.0+cu130, torchvision==0.26.0+cu130, torchaudio==2.11.0+cu130
- All correctly specified in backend/requirements.txt
- If reinstalling needed: `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130`

## WattWatchGuard App (React Native)

### Latest Updates (2026-03-28)
Completely redesigned the WattWatchGuard mobile app with:

1. **Registration Screen** - Professional form with:
   - Staff ID field
   - Full Name field
   - Email Address field (validated)
   - Department field
   - Auto-populated FCM token
   - Real-time form validation
   - Loading states

2. **Dashboard Screen** - Post-registration UI with:
   - User information display
   - Connection status indicator
   - FCM token display
   - Monitoring status badge
   - Check Connection button
   - Logout functionality

3. **Persistent Storage** - Using AsyncStorage:
   - User data saved locally
   - Registration status tracked
   - Auto-login on app restart
   - Clear all data on logout

4. **New Files Created**:
   - `screens/RegistrationScreen.tsx` - Registration form component
   - `screens/DashboardScreen.tsx` - Dashboard after registration
   - `screens/index.ts` - Barrel exports
   - `utils/storageService.ts` - AsyncStorage wrapper
   - `IMPROVEMENTS.md` - Detailed documentation

5. **Updated Files**:
   - `App.tsx` - Main component with screen management
   - `package.json` - Added @react-native-async-storage/async-storage

### Registration Flow
1. Launch app → Request notification permissions
2. Generate FCM token from Firebase
3. Show registration screen
4. User enters: staff_id, name, email, department
5. POST to AWS API: `https://zwgua3w3sb.execute-api.ap-south-1.amazonaws.com/prod/register-token`
6. Save to DynamoDB with FCM token
7. Show dashboard with all registered info
8. Can logout to re-register or register different device

### Key Features
- ✅ Form validation with error messages
- ✅ Modern UI with Tailwind-inspired design
- ✅ Persistent login (auto-login on restart)
- ✅ Error handling with retry logic
- ✅ Loading states and spinners
- ✅ Professional card-based layout
- ✅ DynamoDB integration
- ✅ FCM token auto-sync
