import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { HeartPulse, Eye, EyeOff, Loader2 } from 'lucide-react';
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
    const message = err.response?.data?.message;
    const errorCode = err.response?.data?.data?.errorCode;

    if (message) {
      const errorMap: Record<string, string> = {
        'Invalid credentials': 'E-posta veya şifre hatalı',
        'User not found': 'Kullanıcı bulunamadı',
        'Account disabled': 'Hesabınız devre dışı bırakılmış',
        'Too many attempts': 'Çok fazla deneme yaptınız. Lütfen daha sonra tekrar deneyin',
      };
      return errorMap[message] || message;
    }

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
    <div className="min-h-screen flex items-center justify-center auth-bg p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="h-16 w-16 bg-gradient-to-br from-[#047857] to-[#065f46] rounded-2xl flex items-center justify-center shadow-lg mb-4">
            <HeartPulse className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-semibold text-[#1a2e28]" style={{ fontFamily: 'var(--font-serif)' }}>
            Hoş Geldiniz
          </h1>
          <p className="text-[#5f7068] text-sm mt-1">
            Sağlık sigortası asistanınıza erişmek için giriş yapın
          </p>
        </div>

        <Card className="border-[#e2e8e5] shadow-lg shadow-[#047857]/5">
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div
                  role="alert"
                  aria-live="polite"
                  className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl"
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
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Şifre</Label>
                  {onForgotPassword && (
                    <button
                      type="button"
                      onClick={onForgotPassword}
                      className="text-xs text-[#047857] hover:text-[#065f46] font-medium"
                    >
                      Şifremi unuttum
                    </button>
                  )}
                </div>
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  autoComplete="current-password"
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="text-[#9aada2] hover:text-[#5f7068] transition-colors"
                      aria-label={showPassword ? 'Şifreyi gizle' : 'Şifreyi göster'}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full h-11 rounded-xl bg-[#047857] hover:bg-[#065f46] disabled:opacity-50 text-white font-medium text-sm transition-all shadow-sm hover:shadow flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Giriş yapılıyor...
                  </>
                ) : (
                  'Giriş Yap'
                )}
              </button>
            </form>

            <div className="mt-6 pt-6 border-t border-[#e2e8e5] text-center">
              <p className="text-sm text-[#5f7068]">
                Henüz hesabınız yok mu?{' '}
                <button
                  type="button"
                  onClick={onSwitchToSignUp}
                  className="text-[#047857] hover:text-[#065f46] font-semibold"
                >
                  Kayıt Ol
                </button>
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
