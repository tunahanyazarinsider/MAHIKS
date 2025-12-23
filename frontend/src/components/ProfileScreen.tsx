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
      const message = error.response?.data?.message || 'Şifre güncellenirken bir hata oluştu.';
      
      if (message.toLowerCase().includes('incorrect') || message.toLowerCase().includes('wrong')) {
        setErrors(prev => ({ ...prev, currentPassword: 'Mevcut şifre hatalı' }));
      } else {
        toast.error(message);
      }
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4">
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
      <main className="max-w-3xl mx-auto p-6 space-y-6">
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
              {/* Current Password */}
              <div className="space-y-2">
                <Label htmlFor="currentPassword">Mevcut Şifre</Label>
                <div className="relative">
                  <Input
                    id="currentPassword"
                    type={showPasswords.current ? 'text' : 'password'}
                    placeholder="Mevcut şifrenizi girin"
                    value={passwordData.currentPassword}
                    onChange={(e) => setPasswordData(prev => ({ ...prev, currentPassword: e.target.value }))}
                    disabled={isUpdatingPassword}
                    required
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPasswords(prev => ({ ...prev, current: !prev.current }))}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label={showPasswords.current ? 'Şifreyi gizle' : 'Şifreyi göster'}
                    tabIndex={-1}
                  >
                    {showPasswords.current ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.currentPassword && (
                  <p className="text-sm text-red-500" role="alert">{errors.currentPassword}</p>
                )}
              </div>

              {/* New Password */}
              <div className="space-y-2">
                <Label htmlFor="newPassword">Yeni Şifre</Label>
                <div className="relative">
                  <Input
                    id="newPassword"
                    type={showPasswords.new ? 'text' : 'password'}
                    placeholder="Yeni şifrenizi girin"
                    value={passwordData.newPassword}
                    onChange={(e) => setPasswordData(prev => ({ ...prev, newPassword: e.target.value }))}
                    disabled={isUpdatingPassword}
                    required
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPasswords(prev => ({ ...prev, new: !prev.new }))}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label={showPasswords.new ? 'Şifreyi gizle' : 'Şifreyi göster'}
                    tabIndex={-1}
                  >
                    {showPasswords.new ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.newPassword ? (
                  <p className="text-sm text-red-500" role="alert">{errors.newPassword}</p>
                ) : (
                  <p className="text-xs text-gray-500">Şifre en az 8 karakter olmalıdır</p>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Yeni Şifre (Tekrar)</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showPasswords.confirm ? 'text' : 'password'}
                    placeholder="Yeni şifrenizi tekrar girin"
                    value={passwordData.confirmPassword}
                    onChange={(e) => setPasswordData(prev => ({ ...prev, confirmPassword: e.target.value }))}
                    disabled={isUpdatingPassword}
                    required
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPasswords(prev => ({ ...prev, confirm: !prev.confirm }))}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label={showPasswords.confirm ? 'Şifreyi gizle' : 'Şifreyi göster'}
                    tabIndex={-1}
                  >
                    {showPasswords.confirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="text-sm text-red-500" role="alert">{errors.confirmPassword}</p>
                )}
              </div>

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