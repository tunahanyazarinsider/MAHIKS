import { useState } from 'react';
import { LoginScreen } from './components/LoginScreen';
import { SignUpScreen } from './components/SignUpScreen';
import { ChatScreen } from './components/ChatScreen';
import { ProfileScreen } from './components/ProfileScreen';
import { Toaster } from './components/ui/sonner';

type View = 'signin' | 'signup' | 'chat' | 'profile';

interface UserData {
  email: string;
  name: string;
}

export default function App() {
  const [currentView, setCurrentView] = useState<View>('signin');
  const [user, setUser] = useState<UserData | null>(null);

  const handleLogin = (email: string) => {
    // In a real app, you would fetch the user's name from the backend
    // For now, we'll use a default name or extract from email
    setUser({ email, name: 'User' });
    setCurrentView('chat');
  };

  const handleSignUp = (email: string, name: string) => {
    setUser({ email, name });
    setCurrentView('chat');
  };

  const handleLogout = () => {
    setUser(null);
    setCurrentView('signin');
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

  const handleUpdateProfile = (name: string, email: string) => {
    if (user) {
      setUser({ ...user, name, email });
    }
  };

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
        />
      )}
      <Toaster />
    </>
  );
}
