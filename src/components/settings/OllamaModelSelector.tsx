import React, { useState, useEffect } from 'react';

/** 
 * Component responsible for fetching and displaying available Ollama models in the settings UI.
 * This component calls /api/ollama/health to populate configuration options needed for future runs.
 */
const OllamaModelSelector: React.FC = () => {
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(''); // NEW STATE: Holds the user's selection
  const [isLoading, setIsLoading] = useState(true);
  const [serviceStatus, setServiceStatus] = useState<'online' | 'offline' | null>(null);

  // Function to fetch service status and models
  const fetchOllamaConfig = async () => {
    try {
      const response = await fetch('/api/ollama/health'); // Call the dedicated health endpoint

      if (response.status === 200) {
        const data = await response.json();
        setServiceStatus('online');
        // Set models only if they are available and the service is online
        if (data.availableModels && Array.isArray(data.availableModels)) {
          setModels(data.availableModels);
        } 
      } else if (response.status === 503) {
        // Service explicitly reported it was offline/unreachable
        setServiceStatus('offline');
      } else {
        // Other critical server errors
        setServiceStatus('failure');
      }
  }

  useEffect(() => {
    fetchOllamaConfig();
  }, []);

  return (
    <div className="p-6 bg-gray-50 rounded-lg shadow-md border">
      <h2 className="text-xl font-semibold mb-4">⚙️ Ollama Service Configuration</h2>

      {/* Status Indicator */}
      <div className="mb-4 p-3 text-sm rounded" 
           style={{ borderColor: serviceStatus === 'online' ? '#10B981' : (serviceStatus === 'offline' ? '#EF4444' : '#F59E0B') }}>
        <p><strong>Service Status:</strong> {isLoading ? 'Checking...' : 
          serviceStatus === 'online' ? '✅ Online and operational.' : 
          serviceStatus === 'offline' ? '❌ Offline. Service is unreachable.' : '⚠️ Unknown state.'}</p>
      </div>

      {/* Model Selection Dropdown */}
      <div className="mb-4">
        <label htmlFor="ollamaModel" className="block text-sm font-medium mb-1">Select Primary LLM:</label>
        <select 
          id="ollamaModel" 
          className="w-full p-2 border rounded bg-white"
          disabled={isLoading || models.length === 0}
          value={selectedModel} // <-- Using the state for controlled component
          onChange={(e) => setSelectedModel(e.target.value)} // <-- Handling model selection change
        >
          <option value="" disabled>Please select a model...</option>
          {models.map((model) => (
            <option key={model}>{model}</option>
          ))}
        </select>
      </div>

       {/* Placeholder for Model-Specific Configuration */}
    </div>
  );
};

export default OllamaModelSelector;
EOF'