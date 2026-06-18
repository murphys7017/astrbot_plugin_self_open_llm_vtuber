import { Box, HStack } from '@chakra-ui/react';
import React, { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { canvasStyles } from './canvas-styles';
import { useWSStatus } from '@/hooks/canvas/use-ws-status';

// Type definitions
interface StatusContentProps {
  textKey: string
}

// Reusable components
const StatusContent: React.FC<StatusContentProps> = ({ textKey }) => {
  const { t } = useTranslation();
  return t(textKey);
};
const MemoizedStatusContent = memo(StatusContent);

// Main component
const WebSocketStatus = memo((): JSX.Element => {
  const {
    color, textKey, handleClick, isDisconnected,
  } = useWSStatus();

  return (
    <Box
      {...canvasStyles.wsStatus.container}
      backgroundColor="rgba(10, 10, 10, 0.78)"
      onClick={handleClick}
      cursor={isDisconnected ? 'pointer' : 'default'}
      _hover={{
        borderColor: isDisconnected ? 'var(--olv-border-strong)' : 'var(--olv-border)',
      }}
    >
      <HStack gap="2">
        <Box
          width="7px"
          height="7px"
          borderRadius="999px"
          backgroundColor={color}
          boxShadow={`0 0 0 3px color-mix(in srgb, ${color} 20%, transparent)`}
        />
        <MemoizedStatusContent textKey={textKey} />
      </HStack>
    </Box>
  );
});

WebSocketStatus.displayName = 'WebSocketStatus';

export default WebSocketStatus;
