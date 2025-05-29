import { useState } from 'react';
import { Button } from '@/components/ui/button';

const COMMON_EMOJIS = [
  '📝', '📄', '📁', '📊', '📈', '📋',
  '🏠', '💼', '🎯', '🚀', '💡', '⚡',
  '📚', '🔬', '🎨', '🎵', '📷', '🍕',
  '🌟', '💎', '🔥', '🌈', '🎉', '🎊',
  '💰', '📱', '💻', '🖥️', '⌨️', '🖱️',
  '🌍', '🗺️', '📍', '🏢', '🏪', '🏫'
];

interface EmojiPickerProps {
  currentEmoji?: string;
  onEmojiSelect: (emoji: string) => void;
  onClose: () => void;
}

export const EmojiPicker = ({ currentEmoji, onEmojiSelect, onClose }: EmojiPickerProps) => {
  return (
    <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 p-3">
      <div className="grid grid-cols-6 gap-1 w-48">
        {COMMON_EMOJIS.map((emoji) => (
          <Button
            key={emoji}
            variant={currentEmoji === emoji ? "secondary" : "ghost"}
            size="sm"
            className="w-8 h-8 p-0 text-lg hover:bg-gray-100"
            onClick={() => {
              onEmojiSelect(emoji);
              onClose();
            }}
          >
            {emoji}
          </Button>
        ))}
      </div>
    </div>
  );
}; 