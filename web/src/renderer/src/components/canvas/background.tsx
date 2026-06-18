import { Box, Image } from '@chakra-ui/react';
import { memo, useEffect, useRef, useState } from 'react';
import { canvasStyles } from './canvas-styles';
import { useCamera } from '@/context/camera-context';
import { useBgUrl } from '@/context/bgurl-context';

const Background = memo(({ children }: { children?: React.ReactNode }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [imageLoadFailed, setImageLoadFailed] = useState(false);
  const {
    backgroundStream, isBackgroundStreaming, startBackgroundCamera, stopBackgroundCamera,
  } = useCamera();
  const { useCameraBackground, backgroundUrl } = useBgUrl();

  useEffect(() => {
    if (useCameraBackground) {
      startBackgroundCamera();
    } else {
      stopBackgroundCamera();
    }
  }, [useCameraBackground, startBackgroundCamera, stopBackgroundCamera]);

  useEffect(() => {
    if (videoRef.current && backgroundStream) {
      videoRef.current.srcObject = backgroundStream;
    }
  }, [backgroundStream]);

  useEffect(() => {
    setImageLoadFailed(false);
  }, [backgroundUrl]);

  return (
    <Box {...canvasStyles.background.container}>
      {useCameraBackground ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{
            ...canvasStyles.background.video,
            display: isBackgroundStreaming ? 'block' : 'none',
            transform: 'scaleX(-1)',
          }}
        />
      ) : (
        !imageLoadFailed && (
          <Image
            {...canvasStyles.background.image}
            src={backgroundUrl}
            alt=""
            aria-hidden="true"
            onError={() => setImageLoadFailed(true)}
          />
        )
      )}
      <Box
        position="absolute"
        inset="0"
        zIndex={2}
        pointerEvents="none"
        background="linear-gradient(180deg, rgba(10,10,10,0.18), rgba(10,10,10,0.38))"
      />
      {children}
    </Box>
  );
});

Background.displayName = 'Background';

export default Background;
