import { useState, useEffect } from 'react';
import { LoginScreen } from './components/LoginScreen';
import { SignUpScreen } from './components/SignUpScreen';
import { ChatScreen } from './components/ChatScreen';
import { ProfileScreen } from './components/ProfileScreen';
import { Toaster } from './components/ui/sonner';
import { validateToken, logout as apiLogout, changePassword, updateProfile } from './api/UserApi';
import { HeartPulse } from 'lucide-react';

type View = 'signin' | 'signup' | 'chat' | 'profile';

interface UserData {
  email: string;
  name: string;
}

// Loading screen component
function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <div className="h-16 w-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse">
          <HeartPulse className="h-8 w-8 text-white" />
        </div>
        <p className="text-gray-600">Yükleniyor...</p>
      </div>
    </div>
  );
}

export default function App() {
  const [currentView, setCurrentView] = useState<View>('signin');
  const [user, setUser] = useState<UserData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing token on app start
  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem('token');
      const savedUser = localStorage.getItem('user');

      if (token && savedUser) {
        try {
          const isValid = await validateToken();
          if (isValid) {
            setUser(JSON.parse(savedUser));
            setCurrentView('chat');
          } else {
            // Token invalid, clear storage
            localStorage.removeItem('token');
            localStorage.removeItem('user');
          }
        } catch {
          // Validation failed, clear storage
          localStorage.removeItem('token');
          localStorage.removeItem('user');
        }
      }

      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  // Persist user data when it changes
  useEffect(() => {
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    }
  }, [user]);

  const handleLogin = (email: string, name: string) => {
    const userData = { email, name };
    setUser(userData);
    setCurrentView('chat');
  };

  const handleSignUp = (email: string, name: string) => {
    const userData = { email, name };
    setUser(userData);
    setCurrentView('chat');
  };

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // Even if API call fails, clear local storage
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      setUser(null);
      setCurrentView('signin');
    }
  };

  const handleSwitchToSignUp = () => {
    setCurrentView('signup');
  };

  const handleSwitchToSignIn = () => {
    setCurrentView('signin');
  };

  const handleOpenProfile = () => {
    setCurrentView('profile');
  };

  const handleBackToChat = () => {
    setCurrentView('chat');
  };

  const handleUpdateProfile = async (name: string, email: string) => {
    if (user) {
      try {
        await updateProfile({ name, email });
        setUser({ ...user, name, email });
      } catch {
        throw new Error('Profil güncellenemedi');
      }
    }
  };

  const handleChangePassword = async (currentPassword: string, newPassword: string) => {
    await changePassword(currentPassword, newPassword);
  };

  // Show loading screen while checking auth
  if (isLoading) {
    return <LoadingScreen />;
  }

  return (
    <>
      {currentView === 'signin' && (
        <LoginScreen 
          onLogin={handleLogin} 
          onSwitchToSignUp={handleSwitchToSignUp}
        />
      )}
      {currentView === 'signup' && (
        <SignUpScreen 
          onSignUp={handleSignUp}
          onSwitchToSignIn={handleSwitchToSignIn}
        />
      )}
      {currentView === 'chat' && user && (
        <ChatScreen 
          userEmail={user.email}
          userName={user.name}
          onLogout={handleLogout}
          onOpenProfile={handleOpenProfile}
        />
      )}
      {currentView === 'profile' && user && (
        <ProfileScreen
          userEmail={user.email}
          userName={user.name}
          onBack={handleBackToChat}
          onLogout={handleLogout}
          onUpdateProfile={handleUpdateProfile}
          onChangePassword={handleChangePassword}
        />
      )}
      <Toaster position="top-center" richColors />
    </>
  );
}