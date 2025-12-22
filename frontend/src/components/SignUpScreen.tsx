import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { HeartPulse, Eye, EyeOff } from 'lucide-react';
import { register } from '../api/UserApi';

interface SignUpScreenProps {
  onSignUp: (email: string, name: string) => void;
  onSwitchToSignIn: () => void;
}

export function SignUpScreen({ onSignUp, onSwitchToSignIn }: SignUpScreenProps) {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [showPasswords, setShowPasswords] = useState({
    password: false,
    confirmPassword: false
  });
  const [errors, setErrors] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
    general: ''
  });
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = (): boolean => {
    const newErrors = {
      fullName: '',
      email: '',
      password: '',
      confirmPassword: '',
      general: ''
    };
    let isValid = true;

    if (!formData.fullName.trim()) {
      newErrors.fullName = 'Ad soyad gereklidir';
      isValid = false;
    }

    if (!formData.email.trim()) {
      newErrors.email = 'E-posta gereklidir';
      isValid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Geçerli bir e-posta adresi girin';
      isValid = false;
    }

    if (formData.password.length < 8) {
      newErrors.password = 'Şifre en az 8 karakter olmalıdır';
      isValid = false;
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Şifreler eşleşmiyor';
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  const getErrorMessage = (err: any): string => {
    // Backend returns: { status, message, data: { errorCode } }
    const message = err.response?.data?.message;
    const errorCode = err.response?.data?.data?.errorCode;
    
    if (message) {
      // Map English messages to Turkish
      const errorMap: Record<string, string> = {
        'Email already registered': 'Bu e-posta adresi zaten kayıtlı',
        'Invalid email format': 'Geçersiz e-posta formatı',
        'Password too weak': 'Şifre çok zayıf',
        'User with same email already exists': 'Bu e-posta adresi zaten kayıtlı',
      };
      return errorMap[message] || message;
    }

    // Fallback to error codes
    if (errorCode) {
      const codeMap: Record<string, string> = {
        'USER_ALREADY_EXISTS': 'Bu e-posta adresi zaten kayıtlı',
        'INVALID_EMAIL': 'Geçersiz e-posta formatı',
      };
      return codeMap[errorCode] || 'Bir hata oluştu';
    }
    
    if (err.message === 'Network Error') {
      return 'Bağlantı hatası. Lütfen internet bağlantınızı kontrol edin.';
    }
    
    return 'Kayıt sırasında bir hata oluştu. Lütfen tekrar deneyin.';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    setIsLoading(true);
    setErrors(prev => ({ ...prev, general: '' }));

    try {
      const response = await register(formData.fullName.trim(), formData.email.trim(), formData.password);
      localStorage.setItem('token', response.access_token);
      onSignUp(response.user.email, response.user.display_name);
    } catch (error: any) {
      const message = getErrorMessage(error);
      
      if (message.includes('e-posta') && message.includes('kayıtlı')) {
        setErrors(prev => ({ ...prev, email: message }));
      } else {
        setErrors(prev => ({ ...prev, general: message }));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (field: keyof typeof formData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear related errors on change
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
    if (field === 'password' && errors.confirmPassword) {
      setErrors(prev => ({ ...prev, confirmPassword: '' }));
    }
  };

  const PasswordField = ({
    id,
    label,
    value,
    onChange,
    error,
    hint,
    showKey
  }: {
    id: string;
    label: string;
    value: string;
    onChange: (value: string) => void;
    error?: string;
    hint?: string;
    showKey: 'password' | 'confirmPassword';
  }) => (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative flex items-center">
        <Input
          id={id}
          type={showPasswords[showKey] ? 'text' : 'password'}
          placeholder="••••••••"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={isLoading}
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-blue-600 rounded-full flex items-center justify-center">
              <HeartPulse className="h-8 w-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl text-center">Hesap Oluştur</CardTitle>
          <CardDescription className="text-center">
            Sağlık sigortası asistanınıza erişmek için kayıt olun
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {errors.general && (
              <div 
                role="alert"
                aria-live="polite"
                className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md"
              >
                {errors.general}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="fullName">Ad Soyad</Label>
              <Input
                id="fullName"
                type="text"
                placeholder="Adınızı ve soyadınızı girin"
                value={formData.fullName}
                onChange={(e) => handleChange('fullName', e.target.value)}
                disabled={isLoading}
                aria-describedby={errors.fullName ? 'fullName-error' : undefined}
                autoComplete="name"
                required
              />
              {errors.fullName && (
                <p id="fullName-error" className="text-sm text-red-500" role="alert">
                  {errors.fullName}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">E-posta</Label>
              <Input
                id="email"
                type="email"
                placeholder="ornek@email.com"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                disabled={isLoading}
                aria-describedby={errors.email ? 'email-error' : undefined}
                autoComplete="email"
                required
              />
              {errors.email && (
                <p id="email-error" className="text-sm text-red-500" role="alert">
                  {errors.email}
                </p>
              )}
            </div>

            <PasswordField
              id="password"
              label="Şifre"
              value={formData.password}
              onChange={(value) => handleChange('password', value)}
              error={errors.password}
              hint="En az 8 karakter"
              showKey="password"
            />

            <PasswordField
              id="confirmPassword"
              label="Şifre (Tekrar)"
              value={formData.confirmPassword}
              onChange={(value) => handleChange('confirmPassword', value)}
              error={errors.confirmPassword}
              showKey="confirmPassword"
            />

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Kayıt yapılıyor...' : 'Kayıt Ol'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Zaten hesabınız var mı?{' '}
              <button
                type="button"
                onClick={onSwitchToSignIn}
                className="text-blue-600 hover:underline font-medium"
              >
                Giriş Yap
              </button>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}