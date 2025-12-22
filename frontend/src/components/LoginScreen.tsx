import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { HeartPulse, Eye, EyeOff } from 'lucide-react';
import { login } from '../api/UserApi';

interface LoginScreenProps {
  onLogin: (email: string, name: string) => void;
  onSwitchToSignUp: () => void;
  onForgotPassword?: () => void;
}

export function LoginScreen({ onLogin, onSwitchToSignUp, onForgotPassword }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getErrorMessage = (err: any): string => {
    // Backend returns: { status, message, data: { errorCode } }
    const message = err.response?.data?.message;
    const errorCode = err.response?.data?.data?.errorCode;
    
    if (message) {
      // Map English messages to Turkish
      const errorMap: Record<string, string> = {
        'Invalid credentials': 'E-posta veya şifre hatalı',
        'User not found': 'Kullanıcı bulunamadı',
        'Account disabled': 'Hesabınız devre dışı bırakılmış',
        'Too many attempts': 'Çok fazla deneme yaptınız. Lütfen daha sonra tekrar deneyin',
      };
      return errorMap[message] || message;
    }

    // Fallback to error codes
    if (errorCode) {
      const codeMap: Record<string, string> = {
        'INVALID_CREDENTIALS': 'E-posta veya şifre hatalı',
        'USER_NOT_FOUND': 'Kullanıcı bulunamadı',
        'ACCOUNT_DISABLED': 'Hesabınız devre dışı bırakılmış',
      };
      return codeMap[errorCode] || 'Bir hata oluştu';
    }
    
    if (err.message === 'Network Error') {
      return 'Bağlantı hatası. Lütfen internet bağlantınızı kontrol edin.';
    }
    
    return 'Giriş sırasında bir hata oluştu. Lütfen tekrar deneyin.';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email || !password) {
      setError('Lütfen tüm alanları doldurun.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await login(email, password);
      localStorage.setItem('token', response.access_token);
      onLogin(response.user.email, response.user.display_name);
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-blue-600 rounded-full flex items-center justify-center">
              <HeartPulse className="h-8 w-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl text-center">Hoş Geldiniz</CardTitle>
          <CardDescription className="text-center">
            Sağlık sigortası asistanınıza erişmek için giriş yapın
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div 
                role="alert"
                aria-live="polite"
                className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md"
              >
                {error}
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="email">E-posta</Label>
              <Input
                id="email"
                type="email"
                placeholder="ornek@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
                autoComplete="email"
                aria-describedby={error ? 'login-error' : undefined}
              />
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Şifre</Label>
                {onForgotPassword && (
                  <button
                    type="button"
                    onClick={onForgotPassword}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Şifremi unuttum
                  </button>
                )}
              </div>
              <div className="relative flex items-center">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  autoComplete="current-password"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 text-gray-400 hover:text-gray-600"
                  aria-label={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
            
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Henüz hesabınız yok mu?{' '}
              <button
                type="button"
                onClick={onSwitchToSignUp}
                className="text-blue-600 hover:underline font-medium"
              >
                Kayıt Ol
              </button>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}