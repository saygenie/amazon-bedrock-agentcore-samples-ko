import { useState } from 'react';
import { AlertCircle, CheckCircle, Loader, Layers, User, MessageCircle, X } from 'lucide-react';

const LongTermMemoryForm = ({ onMemoryFetch, memoryConfig, availableNamespaces }) => {
  const [formData, setFormData] = useState({
    namespace: '',
    max_results: 20
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // 누락된 값을 수집하는 모달 상태
  const [showModal, setShowModal] = useState(false);
  const [modalData, setModalData] = useState({
    originalNamespace: '',
    missingValues: {},
    resolvedNamespace: ''
  });

  // namespace의 자리 표시자를 감지하는 도우미 함수
  const detectPlaceholders = (namespace) => {
    const placeholderPattern = /\{(\w+)\}/g;
    const placeholders = [];
    let match;
    
    while ((match = placeholderPattern.exec(namespace)) !== null) {
      placeholders.push(match[1]);
    }
    
    return placeholders;
  };

  // 사용 가능한 값으로 namespace를 완성하는 도우미 함수
  const resolveNamespace = (namespace, values = {}) => {
    let resolved = namespace;
    
    // 제공된 값을 사용하고, 없으면 memoryConfig로 대체
    const allValues = {
      actorId: values.actorId || memoryConfig.actor_id,
      sessionId: values.sessionId || memoryConfig.session_id,
      ...values
    };
    
    // 모든 자리 표시자 교체
    Object.entries(allValues).forEach(([key, value]) => {
      if (value && value.trim()) {
        resolved = resolved.replace(new RegExp(`\\{${key}\\}`, 'g'), value);
      }
    });
    
    return resolved;
  };

  // 누락된 값을 가져오는 도우미 함수
  const getMissingValues = (namespace) => {
    const placeholders = detectPlaceholders(namespace);
    const missing = {};
    
    placeholders.forEach(placeholder => {
      const configKey = placeholder === 'actorId' ? 'actor_id' : 
                       placeholder === 'sessionId' ? 'session_id' : placeholder;
      
      if (!memoryConfig[configKey] || !memoryConfig[configKey].trim()) {
        missing[placeholder] = '';
      }
    });
    
    return missing;
  };

  const handleNamespaceSelection = (originalNamespace) => {
    const missingValues = getMissingValues(originalNamespace);
    
    if (Object.keys(missingValues).length > 0) {
      // 누락된 값을 수집할 모달 표시
      setModalData({
        originalNamespace,
        missingValues,
        resolvedNamespace: resolveNamespace(originalNamespace)
      });
      setShowModal(true);
    } else {
      // 누락된 값이 없으므로 바로 진행
      const resolvedNamespace = resolveNamespace(originalNamespace);
      setFormData(prev => ({ ...prev, namespace: resolvedNamespace }));
      handleAutoFetch({ ...formData, namespace: resolvedNamespace });
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    setError('');
    setSuccess('');
    
    // 수동 입력에서 namespace를 선택하면 자동으로 가져오기
    if (field === 'namespace' && value.trim()) {
      const updatedFormData = { ...formData, [field]: value };
      handleAutoFetch(updatedFormData);
    }
  };

  const handleModalValueChange = (key, value) => {
    setModalData(prev => ({
      ...prev,
      missingValues: {
        ...prev.missingValues,
        [key]: value
      }
    }));
  };

  const handleModalSubmit = () => {
    const resolvedNamespace = resolveNamespace(modalData.originalNamespace, modalData.missingValues);
    setFormData(prev => ({ ...prev, namespace: resolvedNamespace }));
    setShowModal(false);
    handleAutoFetch({ ...formData, namespace: resolvedNamespace });
  };

  const handleModalCancel = () => {
    setShowModal(false);
    setModalData({
      originalNamespace: '',
      missingValues: {},
      resolvedNamespace: ''
    });
  };

  const handleAutoFetch = async (currentFormData) => {
    if (!currentFormData.namespace.trim()) return;
    
    setLoading(true);
    setError('');
    setSuccess('');

    const requestPayload = {
      ...currentFormData,
      memory_id: memoryConfig.memory_id,
      content_type: 'all',
      sort_by: 'timestamp',
      sort_order: 'desc'
    };

    console.log('🚀 Auto-fetching long-term memory:', requestPayload);

    try {
      const response = await fetch('http://localhost:8000/api/agentcore/getLongTermMemory', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestPayload)
      });

      console.log('📡 Response status:', response.status);

      const textResponse = await response.text();
      let data;
      
      try {
        data = JSON.parse(textResponse);
      } catch (parseError) {
        console.error('Non-JSON response from backend:', textResponse);
        throw new Error(`Backend returned non-JSON response (status ${response.status}). Check backend logs.`);
      }

      if (!response.ok) {
        console.error('❌ Error response:', data);
        const errorMessage = data.detail || `Request failed with status ${response.status}`;
        throw new Error(errorMessage);
      }
      console.log('✅ Response data:', data);
      
      if (data.memories && data.memories.length > 0) {
        setSuccess(`Found ${data.memories.length} long-term memory entries!`);
        onMemoryFetch(data.memories);
      } else {
        setSuccess('Query completed successfully.');
        onMemoryFetch([]); // 기본 영역에 빈 상태를 표시하도록 빈 배열 전달
      }

    } catch (err) {
      console.error('❌ Long-term memory fetch error:', err);
      
      // 백엔드에서 구체적인 오류 메시지 파싱
      let errorMessage = 'Failed to fetch long-term memory';
      
      if (err.response?.status === 404) {
        errorMessage = err.response.data?.detail || 'Memory ID or namespace not found. Please verify they exist and you have access permissions.';
      } else if (err.response?.status === 403) {
        errorMessage = err.response.data?.detail || 'Access denied. Please check your AWS credentials and permissions.';
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.namespace.trim()) {
      setError('Namespace is required.');
      return;
    }
    
    setLoading(true);
    setError('');
    setSuccess('');

    const requestPayload = {
      ...formData,
      memory_id: memoryConfig.memory_id,
      content_type: 'all',
      sort_by: 'timestamp',
      sort_order: 'desc'
    };

    console.log('🚀 Sending long-term memory request:', requestPayload);

    try {
      const response = await fetch('http://localhost:8000/api/agentcore/getLongTermMemory', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestPayload)
      });

      console.log('📡 Response status:', response.status);

      const textResponse = await response.text();
      let data;
      
      try {
        data = JSON.parse(textResponse);
      } catch (parseError) {
        console.error('Non-JSON response from backend:', textResponse);
        throw new Error(`Backend returned non-JSON response (status ${response.status}). Check backend logs.`);
      }

      if (!response.ok) {
        console.error('❌ Error response:', data);
        const errorMessage = data.detail || `Request failed with status ${response.status}`;
        throw new Error(errorMessage);
      }
      console.log('✅ Response data:', data);
      
      if (data.memories && data.memories.length > 0) {
        setSuccess(`Found ${data.memories.length} long-term memory entries!`);
        onMemoryFetch(data.memories);
      } else {
        setSuccess('Query completed successfully.');
        onMemoryFetch([]); // 기본 영역에 빈 상태를 표시하도록 빈 배열 전달
      }

    } catch (err) {
      console.error('❌ Long-term memory submit error:', err);
      
      // 백엔드에서 구체적인 오류 메시지 파싱
      let errorMessage = 'Failed to fetch long-term memory';
      
      if (err.response?.status === 404) {
        errorMessage = err.response.data?.detail || 'Memory ID or namespace not found. Please verify they exist and you have access permissions.';
      } else if (err.response?.status === 403) {
        errorMessage = err.response.data?.detail || 'Access denied. Please check your AWS credentials and permissions.';
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  console.log('🔍 LongTermMemoryForm render:', { 
    availableNamespaces, 
    availableNamespacesLength: availableNamespaces.length,
    memoryConfig 
  });

  return (
    <div className="long-term-memory-form">


      <div className="memory-form">
        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="namespace">
              <Layers size={16} />
              Namespace (Required)
            </label>
            {availableNamespaces.length > 0 ? (
              <div className="namespace-selector">
                {availableNamespaces.map((ns, index) => {
                  // 이 namespace에 누락된 값이 있는지 확인
                  const missingValues = getMissingValues(ns.namespace);
                  const hasMissingValues = Object.keys(missingValues).length > 0;
                  
                  // 누락된 값이 없을 때만 완성된 namespace 표시
                  const displayNamespace = hasMissingValues ? ns.namespace : resolveNamespace(ns.namespace);
                  
                  const isSelected = formData.namespace === displayNamespace || 
                                   (!hasMissingValues && formData.namespace === resolveNamespace(ns.namespace));
                  
                  return (
                    <div 
                      key={index}
                      className={`namespace-option ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleNamespaceSelection(ns.namespace)}
                    >
                      <div className="namespace-type">
                        <span className={`type-badge ${ns.type.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}>
                          {(() => {
                            // 표준 AgentCore Strategy 유형
                            const standardTypes = {
                              'SEMANTIC': 'Facts',
                              'USER_PREFERENCE': 'Preferences',
                              'SUMMARIZATION': 'Summaries'
                            };
                            
                            // 표준 유형이면 이해하기 쉬운 이름 사용
                            if (standardTypes[ns.type]) {
                              return standardTypes[ns.type];
                            }
                            
                            // 사용자 지정 유형은 읽기 좋은 형식으로 지정
                            return ns.type
                              .split('_')
                              .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                              .join(' ');
                          })()}
                        </span>
                      </div>
                      <div className="namespace-path">
                        {displayNamespace.split('/').slice(0, -1).join('/') || displayNamespace}
                        {hasMissingValues && (
                          <span className="missing-values-indicator"> (requires values)</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <input
                id="namespace"
                type="text"
                value={formData.namespace}
                onChange={(e) => handleInputChange('namespace', e.target.value)}
                placeholder="e.g., your-namespace/facts, company/user/preferences"
                className="form-input"
                required
              />
            )}
            <div className="form-help">
              {availableNamespaces.length > 0 
                ? `Select from ${availableNamespaces.length} available namespaces discovered from your memory strategies`
                : 'Specify the exact namespace to query (e.g., your-namespace/facts, company/user/preferences)'
              }
            </div>
          </div>



          {loading && (
            <div className="loading-indicator">
              <Loader size={16} className="spinning" />
              <span>Loading memory data...</span>
            </div>
          )}
        </div>

        {/* 상태 메시지 */}
        {error && (
          <div className="status-message error">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="status-message success">
            <CheckCircle size={16} />
            <span>{success}</span>
          </div>
        )}
      </div>

      {/* 누락된 값을 수집하는 모달 */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Complete Namespace Configuration</h3>
              <button className="modal-close" onClick={handleModalCancel}>
                <X size={20} />
              </button>
            </div>
            
            <div className="modal-body">
              <p>This namespace requires additional values:</p>
              <div className="namespace-preview">
                <strong>Namespace:</strong> {modalData.originalNamespace}
              </div>
              
              <div className="missing-values-form">
                {Object.entries(modalData.missingValues).map(([key, value]) => (
                  <div key={key} className="form-group">
                    <label htmlFor={`modal-${key}`}>
                      {key === 'actorId' ? <User size={16} /> : <MessageCircle size={16} />}
                      {key === 'actorId' ? 'Actor ID' : 
                       key === 'sessionId' ? 'Session ID' : key}
                    </label>
                    <input
                      id={`modal-${key}`}
                      type="text"
                      value={value}
                      onChange={(e) => handleModalValueChange(key, e.target.value)}
                      placeholder={key === 'actorId' ? 'e.g., DEFAULT, user123' : 
                                  key === 'sessionId' ? 'e.g., session-abc123' : `Enter ${key}`}
                      className="form-input"
                    />
                  </div>
                ))}
              </div>
              
              <div className="resolved-preview">
                <strong>Resolved namespace:</strong>
                <code>{resolveNamespace(modalData.originalNamespace, modalData.missingValues)}</code>
              </div>
            </div>
            
            <div className="modal-footer">
              <button className="modal-btn cancel" onClick={handleModalCancel}>
                Cancel
              </button>
              <button 
                className="modal-btn submit" 
                onClick={handleModalSubmit}
                disabled={Object.values(modalData.missingValues).some(v => !v.trim())}
              >
                Use Namespace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LongTermMemoryForm;
