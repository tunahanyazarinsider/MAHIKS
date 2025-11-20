import { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Separator } from './ui/separator';
import { HeartPulse, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

interface ProfileScreenProps {
  userEmail: string;
  userName: string;
  onBack: () => void;
  onLogout: () => void;
  onUpdateProfile: (name: string, email: string) => void;
}

export function ProfileScreen({ userEmail, userName, onBack, onLogout, onUpdateProfile }: ProfileScreenProps) {
  const [profileData, setProfileData] = useState({
    name: userName,
    email: userEmail
  });
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState({
    newPassword: '',
    confirmPassword: ''
  });
  const [isEditingProfile, setIsEditingProfile] = useState(false);

  const handleProfileUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (profileData.name.trim() && profileData.email.trim()) {
      onUpdateProfile(profileData.name, profileData.email);
      setIsEditingProfile(false);
      toast.success('Profile updated successfully!');
    }
  };

  const handleCancelEdit = () => {
    setProfileData({
      name: userName,
      email: userEmail
    });
    setIsEditingProfile(false);
  };

  const handlePasswordChange = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Reset errors
    setErrors({ newPassword: '', confirmPassword: '' });

    // Validate
    if (passwordData.newPassword.length < 8) {
      setErrors(prev => ({ ...prev, newPassword: 'Password must be at least 8 characters' }));
      return;
    }

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setErrors(prev => ({ ...prev, confirmPassword: 'Passwords do not match' }));
      return;
    }

    // Simulate password change
    toast.success('Password updated successfully!');
    setPasswordData({
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between max-w-5xl mx-auto">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={onBack}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="h-10 w-10 bg-blue-600 rounded-full flex items-center justify-center">
              <HeartPulse className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1>Profile Settings</h1>
              <p className="text-sm text-gray-500">Manage your account information</p>
            </div>
          </div>
          
          <Button variant="outline" size="sm" onClick={onLogout}>
            Logout
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Profile Information Card */}
        <Card>
          <CardHeader>
            <CardTitle>Profile Information</CardTitle>
            <CardDescription>Your personal account details</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleProfileUpdate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  type="text"
                  value={profileData.name}
                  onChange={(e) => setProfileData(prev => ({ ...prev, name: e.target.value }))}
                  disabled={!isEditingProfile}
                  className={!isEditingProfile ? 'bg-gray-50' : ''}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  value={profileData.email}
                  onChange={(e) => setProfileData(prev => ({ ...prev, email: e.target.value }))}
                  disabled={!isEditingProfile}
                  className={!isEditingProfile ? 'bg-gray-50' : ''}
                  required
                />
              </div>

              {!isEditingProfile ? (
                <Button type="button" variant="outline" className="w-full" onClick={() => setIsEditingProfile(true)}>
                  Edit Profile
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button type="submit" className="flex-1">
                    Save Changes
                  </Button>
                  <Button type="button" variant="outline" className="flex-1" onClick={handleCancelEdit}>
                    Cancel
                  </Button>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Change Password Card */}
        <Card>
          <CardHeader>
            <CardTitle>Change Password</CardTitle>
            <CardDescription>Update your password to keep your account secure</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="currentPassword">Current Password</Label>
                <Input
                  id="currentPassword"
                  type="password"
                  placeholder="Enter current password"
                  value={passwordData.currentPassword}
                  onChange={(e) => setPasswordData(prev => ({ ...prev, currentPassword: e.target.value }))}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="newPassword">New Password</Label>
                <Input
                  id="newPassword"
                  type="password"
                  placeholder="Enter new password"
                  value={passwordData.newPassword}
                  onChange={(e) => setPasswordData(prev => ({ ...prev, newPassword: e.target.value }))}
                  required
                />
                {errors.newPassword && (
                  <p className="text-sm text-red-500">{errors.newPassword}</p>
                )}
                <p className="text-xs text-gray-500">Password must be at least 8 characters</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm New Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="Confirm new password"
                  value={passwordData.confirmPassword}
                  onChange={(e) => setPasswordData(prev => ({ ...prev, confirmPassword: e.target.value }))}
                  required
                />
                {errors.confirmPassword && (
                  <p className="text-sm text-red-500">{errors.confirmPassword}</p>
                )}
              </div>

              <Button type="submit" className="w-full">
                Update Password
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
