import React, { useState, useEffect } from 'react';
import { User, MessageCircle, Search, AlertCircle, CheckCircle, Loader, HelpCircle, Clock, ChevronDown, Database } from 'lucide-react';

const ShortTermMemoryForm = ({ onMemoryFetch, memoryConfig }) => {
  const [formData, setFormData] = useState({
    session_id: '',
    max_results: 20
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchHistory, setSearchHistory] = useState([]);
  const [showActorHistory, setShowActorHistory] = useState(false);
  const [showSessionHistory, setShowSessionHistory] = useState(false);

  // component를 mount할 때 localStorage에서 검색 기록 로드
  useEffect(() => {
    const savedHistory = localStorage.getItem('agentcore-search-history');
    if (savedHistory) {
      try {
        setSearchHistory(JSON.parse(savedHistory));
      } catch (e) {
        console.error('Failed to parse search history:', e);
      }
    }
  }, []);

  // memoryConfig를 prop으로 받으므로 useEffect가 필요하지 않음

  // 검색 내용을 기록에 저장
  const saveToHistory = (actorId, sessionId) => {
    const newEntry = {
      actor_id: actorId,
      session_id: sessionId,
      timestamp: new Date().toISOString(),
      id: Date.now()
    };

    const updatedHistory = [
      newEntry,
      ...searchHistory.filter(item => 
        !(item.actor_id === actorId && item.session_id === sessionId)
      )
    ].slice(0, 10); // 최근 검색 10개만 유지

    setSearchHistory(updatedHistory);
    localStorage.setItem('agentcore-search-history', JSON.stringify(updatedHistory));
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    setError('');
    setSuccess('');
  };

  const handleHistorySelect = (historyItem) => {
    setFormData(prev => ({
      ...prev,
      actor_id: historyItem.actor_id,
      session_id: historyItem.session_id
    }));
    setShowActorHistory(false);
    setShowSessionHistory(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!memoryConfig.actor_id || !memoryConfig.actor_id.trim()) {
      setError('Actor ID is required in configuration');
      return;
    }
    
    if (!formData.session_id.trim()) {
      setError('Session ID is required');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('http://localhost:8000/api/agentcore/getShortTermMemory', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...formData,
          memory_id: memoryConfig.memory_id,
          actor_id: memoryConfig.actor_id
        })
      });

      const textResponse = await response.text();
      let data;
      
      try {
        data = JSON.parse(textResponse);
      } catch (parseError) {
        console.error('Non-JSON response from backend:', textResponse);
        throw new Error(`Backend returned non-JSON response (status ${response.status}). Check backend logs.`);
      }

      if (!response.ok) {
        const errorMessage = data.detail || `Request failed with status ${response.status}`;
        throw new Error(errorMessage);
      }

      // data는 위에서 이미 파싱됨
      
      if (data.memories && data.memories.length > 0) {
        setSuccess(`Found ${data.memories.length} short-term memory entries!`);
        onMemoryFetch(data.memories);
        // 성공한 검색을 기록에 저장
        saveToHistory(formData.actor_id, formData.session_id);
      } else {
        setSuccess('Query completed successfully.');
        onMemoryFetch([]); // 기본 영역에 빈 상태를 표시하도록 빈 배열 전달
      }

    } catch (err) {
      console.error('❌ Short-term memory fetch error:', err);
      
      // 백엔드에서 구체적인 오류 메시지 파싱
      let errorMessage = 'Failed to fetch short-term memory';
      
      if (err.response?.status === 404) {
        errorMessage = err.response.data?.detail || 'Memory ID not found. Please verify the Memory ID exists and you have access permissions.';
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

  const clearHistory = () => {
    setSearchHistory([]);
    localStorage.removeItem('agentcore-search-history');
  };

  const getUniqueActorIds = () => {
    const actors = [...new Set(searchHistory.map(item => item.actor_id))];
    return actors.slice(0, 5);
  };

  const getUniqueSessionIds = () => {
    const sessions = [...new Set(searchHistory.map(item => item.session_id))];
    return sessions.slice(0, 5);
  };

  return (
    <div className="short-term-memory-form">


      <form onSubmit={handleSubmit} className="memory-form">
        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="session_id">
              <MessageCircle size={16} />
              Session ID (Required)
            </label>
            <input
              id="session_id"
              type="text"
              value={formData.session_id}
              onChange={(e) => handleInputChange('session_id', e.target.value)}
              placeholder="e.g., session-abc123, conv-456def"
              className="form-input"
              required
            />
            <div className="form-help">
              Specify the exact session identifier to query (e.g., session-abc123, conv-456def)
            </div>
          </div>





          <div className="form-group">
            <label>&nbsp;</label>
            <button
              type="submit"
              disabled={loading || !formData.session_id.trim()}
              className="submit-button-inline"
            >
              {loading ? (
                <>
                  <Loader size={16} className="spinning" />
                  Fetching...
                </>
              ) : (
                <>
                  <Search size={16} />
                  Fetch Short-Term Memory
                </>
              )}
            </button>
            <div className="form-help">&nbsp;</div>
          </div>
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



      </form>
    </div>
  );
};

export default ShortTermMemoryForm;
