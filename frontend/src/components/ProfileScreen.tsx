import { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { HeartPulse, ArrowLeft, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

interface ProfileScreenProps {
  userEmail: string;
  userName: string;
  onBack: () => void;
  onLogout: () => void;
  onUpdateProfile: (name: string, email: string) => void;
  onChangePassword?: (currentPassword: string, newPassword: string) => Promise<void>;
}

export function ProfileScreen({ 
  userEmail, 
  userName, 
  onBack, 
  onLogout, 
  onUpdateProfile,
  onChangePassword 
}: ProfileScreenProps) {
  const [profileData, setProfileData] = useState({
    name: userName,
    email: userEmail
  });
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  });
  const [errors, setErrors] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const trimmedName = profileData.name.trim();
    const trimmedEmail = profileData.email.trim();

    if (!trimmedName || !trimmedEmail) {
      toast.error('Lütfen tüm alanları doldurun.');
      return;
    }

    setIsUpdatingProfile(true);
    
    try {
      onUpdateProfile(trimmedName, trimmedEmail);
      setIsEditingProfile(false);
      toast.success('Profil başarıyla güncellendi!');
    } catch (error) {
      toast.error('Profil güncellenirken bir hata oluştu.');
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleCancelEdit = () => {
    setProfileData({
      name: userName,
      email: userEmail
    });
    setIsEditingProfile(false);
  };

  const validatePassword = (): boolean => {
    const newErrors = { currentPassword: '', newPassword: '', confirmPassword: '' };
    let isValid = true;

    if (!passwordData.currentPassword) {
      newErrors.currentPassword = 'Mevcut şifrenizi girin';
      isValid = false;
    }

    if (passwordData.newPassword.length < 8) {
      newErrors.newPassword = 'Şifre en az 8 karakter olmalıdır';
      isValid = false;
    }

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      newErrors.confirmPassword = 'Şifreler eşleşmiyor';
      isValid = false;
    }

    if (passwordData.currentPassword === passwordData.newPassword) {
      newErrors.newPassword = 'Yeni şifre mevcut şifreden farklı olmalıdır';
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validatePassword()) return;

    setIsUpdatingPassword(true);

    try {
      if (onChangePassword) {
        await onChangePassword(passwordData.currentPassword, passwordData.newPassword);
      }
      
      toast.success('Şifre başarıyla güncellendi!');
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      });
      setErrors({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Şifre güncellenirken bir hata oluştu.';
      
      if (message.toLowerCase().includes('incorrect') || message.toLowerCase().includes('wrong')) {
        setErrors(prev => ({ ...prev, currentPassword: 'Mevcut şifre hatalı' }));
      } else {
        toast.error(message);
      }
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  const PasswordInput = ({ 
    id, 
    label, 
    value, 
    onChange, 
    placeholder,
    error,
    hint,
    showKey
  }: {
    id: string;
    label: string;
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
    error?: string;
    hint?: string;
    showKey: 'current' | 'new' | 'confirm';
  }) => (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative flex items-center">
        <Input
          id={id}
          type={showPasswords[showKey] ? 'text' : 'password'}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={isUpdatingPassword}
          className="pr-10"
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          required
        />
        <button
          type="button"
          onClick={() => setShowPasswords(prev => ({ ...prev, [showKey]: !prev[showKey] }))}
          className="absolute right-3 text-gray-400 hover:text-gray-600"
          aria-label={showPasswords[showKey] ? 'Şifreyi gizle' : 'Şifreyi göster'}
          tabIndex={-1}
        >
          {showPasswords[showKey] ? (
            <EyeOff className="h-4 w-4" />
          ) : (
            <Eye className="h-4 w-4" />
          )}
        </button>
      </div>
      {error && (
        <p id={`${id}-error`} className="text-sm text-red-500" role="alert">
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-gray-500">
          {hint}
        </p>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-4 md:px-6 py-4">
        <div className="flex items-center justify-between max-w-5xl mx-auto">
          <div className="flex items-center gap-3">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={onBack}
              aria-label="Geri dön"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="h-10 w-10 bg-blue-600 rounded-full flex items-center justify-center">
              <HeartPulse className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Profil Ayarları</h1>
              <p className="text-sm text-gray-500">Hesap bilgilerinizi yönetin</p>
            </div>
          </div>
          
          <Button 
            variant="outline" 
            size="sm" 
            onClick={onLogout}
            aria-label="Çıkış yap"
          >
            Çıkış Yap
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto p-4 md:p-6 space-y-6">
        {/* Profile Information Card */}
        <Card>
          <CardHeader>
            <CardTitle>Profil Bilgileri</CardTitle>
            <CardDescription>Hesap bilgilerinizi görüntüleyin ve düzenleyin</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleProfileUpdate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Ad Soyad</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="Adınızı ve soyadınızı girin"
                  value={profileData.name}
                  onChange={(e) => setProfileData(prev => ({ ...prev, name: e.target.value }))}
                  disabled={!isEditingProfile || isUpdatingProfile}
                  className={!isEditingProfile ? 'bg-gray-50' : ''}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">E-posta</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="ornek@email.com"
                  value={profileData.email}
                  onChange={(e) => setProfileData(prev => ({ ...prev, email: e.target.value }))}
                  disabled={!isEditingProfile || isUpdatingProfile}
                  className={!isEditingProfile ? 'bg-gray-50' : ''}
                  required
                />
              </div>

              {!isEditingProfile ? (
                <Button 
                  type="button" 
                  variant="outline" 
                  className="w-full" 
                  onClick={() => setIsEditingProfile(true)}
                >
                  Profili Düzenle
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button 
                    type="submit" 
                    className="flex-1"
                    disabled={isUpdatingProfile}
                  >
                    {isUpdatingProfile ? 'Kaydediliyor...' : 'Değişiklikleri Kaydet'}
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    className="flex-1" 
                    onClick={handleCancelEdit}
                    disabled={isUpdatingProfile}
                  >
                    İptal
                  </Button>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Change Password Card */}
        <Card>
          <CardHeader>
            <CardTitle>Şifre Değiştir</CardTitle>
            <CardDescription>Hesabınızı güvende tutmak için şifrenizi düzenli olarak güncelleyin</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <PasswordInput
                id="currentPassword"
                label="Mevcut Şifre"
                value={passwordData.currentPassword}
                onChange={(value) => setPasswordData(prev => ({ ...prev, currentPassword: value }))}
                placeholder="Mevcut şifrenizi girin"
                error={errors.currentPassword}
                showKey="current"
              />

              <PasswordInput
                id="newPassword"
                label="Yeni Şifre"
                value={passwordData.newPassword}
                onChange={(value) => setPasswordData(prev => ({ ...prev, newPassword: value }))}
                placeholder="Yeni şifrenizi girin"
                error={errors.newPassword}
                hint="Şifre en az 8 karakter olmalıdır"
                showKey="new"
              />

              <PasswordInput
                id="confirmPassword"
                label="Yeni Şifre (Tekrar)"
                value={passwordData.confirmPassword}
                onChange={(value) => setPasswordData(prev => ({ ...prev, confirmPassword: value }))}
                placeholder="Yeni şifrenizi tekrar girin"
                error={errors.confirmPassword}
                showKey="confirm"
              />

              <Button 
                type="submit" 
                className="w-full"
                disabled={isUpdatingPassword}
              >
                {isUpdatingPassword ? 'Güncelleniyor...' : 'Şifreyi Güncelle'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}