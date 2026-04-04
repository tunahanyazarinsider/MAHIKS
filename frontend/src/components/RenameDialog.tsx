import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';

interface RenameDialogProps {
  open: boolean;
  currentTitle: string;
  onOpenChange: (open: boolean) => void;
  onRename: (newTitle: string) => void;
}

export function RenameDialog({ open, currentTitle, onOpenChange, onRename }: RenameDialogProps) {
  const [title, setTitle] = useState(currentTitle);

  useEffect(() => {
    if (open) {
      setTitle(currentTitle);
    }
  }, [currentTitle, open]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title.trim()) {
      onRename(title.trim());
      onOpenChange(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" onKeyDown={handleKeyDown}>
        <DialogHeader>
          <DialogTitle>Sohbeti Yeniden Adlandır</DialogTitle>
          <DialogDescription>
            Bu sohbet için yeni bir başlık girin.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="title">Sohbet Başlığı</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Sohbet başlığını girin..."
                maxLength={100}
                autoFocus
                aria-describedby="title-hint"
              />
              <p id="title-hint" className="text-xs text-gray-500">
                Maksimum 100 karakter
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              İptal
            </Button>
            <Button type="submit" disabled={!title.trim()}>
              Kaydet
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}