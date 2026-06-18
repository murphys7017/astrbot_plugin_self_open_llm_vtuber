import { createListCollection } from '@chakra-ui/react';
import {
  useState, useEffect, useMemo, useCallback,
} from 'react';
import { ModelInfo, useLive2DConfig } from '@/context/live2d-config-context';
import { useWebSocket } from '@/context/websocket-context';

interface Live2DModelOption {
  label: string;
  value: string;
  description?: string;
}

type ModelDictEntry = {
  name?: string;
  description?: string;
};

export const useLive2dSettings = () => {
  const Live2DConfigContext = useLive2DConfig();
  const { baseUrl, sendMessage } = useWebSocket();

  const initialModelInfo: ModelInfo = {
    url: '',
    kScale: 0.5,
    initialXshift: 0,
    initialYshift: 0,
    emotionMap: {},
    scrollToResize: true,
  };

  const [modelInfo, setModelInfoState] = useState<ModelInfo>(
    Live2DConfigContext?.modelInfo || initialModelInfo,
  );
  const [originalModelInfo, setOriginalModelInfo] = useState<ModelInfo>(
    Live2DConfigContext?.modelInfo || initialModelInfo,
  );
  const [modelOptions, setModelOptions] = useState<Live2DModelOption[]>([]);
  const [modelListStatus, setModelListStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [selectedModelName, setSelectedModelNameState] = useState<string[]>(
    Live2DConfigContext?.modelInfo?.name ? [Live2DConfigContext.modelInfo.name] : [],
  );

  const modelCollection = useMemo(() => createListCollection({
    items: modelOptions.map((model) => ({
      label: model.label,
      value: model.value,
    })),
  }), [modelOptions]);

  useEffect(() => {
    if (Live2DConfigContext?.modelInfo) {
      if (JSON.stringify(Live2DConfigContext.modelInfo) !== JSON.stringify(originalModelInfo)) {
        setOriginalModelInfo(Live2DConfigContext.modelInfo);
        setModelInfoState(Live2DConfigContext.modelInfo);
      }
      if (Live2DConfigContext.modelInfo.name) {
        setSelectedModelNameState([Live2DConfigContext.modelInfo.name]);
      }
    }
  }, [Live2DConfigContext?.modelInfo]);

  useEffect(() => {
    let cancelled = false;

    async function loadModelOptions() {
      setModelListStatus('loading');
      try {
        const response = await fetch(`${baseUrl}/live2ds/model_dict.json`, {
          cache: 'no-store',
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        if (!Array.isArray(payload)) {
          throw new Error('Invalid model dictionary payload');
        }

        const nextOptions = payload
          .filter((item: ModelDictEntry) => typeof item?.name === 'string' && item.name.trim())
          .map((item: ModelDictEntry) => ({
            label: item.name!.trim(),
            value: item.name!.trim(),
            description: typeof item.description === 'string' ? item.description : '',
          }));

        if (!cancelled) {
          setModelOptions(nextOptions);
          setModelListStatus('ready');
        }
      } catch (error) {
        console.error('Failed to load Live2D model list:', error);
        if (!cancelled) {
          setModelListStatus('error');
        }
      }
    }

    void loadModelOptions();

    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  useEffect(() => {
    if (Live2DConfigContext && modelInfo) {
      Live2DConfigContext.setModelInfo(modelInfo);
    }
  }, [modelInfo.pointerInteractive, modelInfo.scrollToResize]);

  const handleInputChange = useCallback((key: keyof ModelInfo, value: ModelInfo[keyof ModelInfo]): void => {
    setModelInfoState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const setSelectedModelName = useCallback((value: string[]): void => {
    const modelName = value[0] ?? '';
    setSelectedModelNameState(modelName ? [modelName] : []);
    if (!modelName) {
      return;
    }
    sendMessage({
      type: 'switch-live2d-model',
      model_name: modelName,
    });
  }, [sendMessage]);

  const handleSave = useCallback((): void => {
    if (Live2DConfigContext && modelInfo) {
      setOriginalModelInfo(modelInfo);
    }
  }, [Live2DConfigContext, modelInfo]);

  const handleCancel = useCallback((): void => {
    setModelInfoState(originalModelInfo);
    if (Live2DConfigContext && originalModelInfo) {
      Live2DConfigContext.setModelInfo(originalModelInfo);
    }
    const originalModelName = originalModelInfo.name ?? '';
    setSelectedModelNameState(originalModelName ? [originalModelName] : []);
    if (originalModelName && originalModelName !== selectedModelName[0]) {
      sendMessage({
        type: 'switch-live2d-model',
        model_name: originalModelName,
      });
    }
  }, [Live2DConfigContext, originalModelInfo, selectedModelName, sendMessage]);

  return {
    modelInfo,
    modelOptions,
    modelCollection,
    modelListStatus,
    selectedModelName,
    setSelectedModelName,
    handleInputChange,
    handleSave,
    handleCancel,
  };
};
