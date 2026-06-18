import { Box, Text, Flex } from '@chakra-ui/react';
import { Avatar, AvatarGroup } from '@/components/ui/avatar';
import { Message } from '@/services/websocket-service';

// Type definitions
interface ChatBubbleProps {
  message: Message;
  isSelected?: boolean;
  onClick?: () => void;
}

// Main component
export function ChatBubble({ message, isSelected, onClick }: ChatBubbleProps): JSX.Element {
  const isAI = message.role === 'ai';

  return (
    <Box
      onClick={onClick}
      cursor="pointer"
      bg={isSelected ? 'rgba(255,255,255,0.08)' : 'transparent'}
      _hover={{ bg: 'rgba(255,255,255,0.05)' }}
      p={2}
      borderRadius="8px"
      transition="background-color 0.2s"
    >
      <Flex gap={3}>
        <AvatarGroup>
          <Avatar
            size="sm"
            name={message.name || (isAI ? 'AI' : 'Me')}
            bg={isAI ? '#111111' : '#ededed'}
            color={isAI ? 'var(--olv-text)' : 'var(--olv-bg)'}
          />
        </AvatarGroup>
        <Box flex={1}>
          <Text fontSize="13px" fontWeight="600" color="var(--olv-text)">
            {message.name || (isAI ? 'AI' : 'Me')}
          </Text>
          <Text
            fontSize="13px"
            color="var(--olv-muted)"
            truncate
          >
            {message.content}
          </Text>
          <Text fontSize="11px" color="var(--olv-subtle)" mt={1}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </Text>
        </Box>
      </Flex>
    </Box>
  );
}
