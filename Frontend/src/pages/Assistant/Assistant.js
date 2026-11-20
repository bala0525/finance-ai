import React, {
  useEffect,
  useRef,
  useState,
} from "react";

import AssistantMessage from "../../components/assistant/AssistantMessage";

import {
  getAssistantConversation,
  sendAssistantMessage,
} from "../../services/assistantService";

import {
  assistantSuggestedQuestions,
  assistantWelcome,
} from "../../data/assistantData";

import "./Assistant.css";

function Assistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const messagesEndRef = useRef(null);

  useEffect(() => {
    let isMounted = true;

    async function loadConversation() {
      try {
        setLoading(true);
        setError("");

        const data = await getAssistantConversation();

        if (isMounted) {
          setMessages(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            "Unable to load the Finance AI Assistant."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadConversation();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, sending]);

  const handleSendMessage = async (event) => {
    event.preventDefault();

    const trimmedMessage = input.trim();

    if (!trimmedMessage || sending) {
      return;
    }

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: trimmedMessage,
    };

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ]);

    setInput("");
    setSending(true);
    setError("");

    try {
      const assistantMessage =
        await sendAssistantMessage(trimmedMessage);

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);
    } catch (requestError) {
      setError(
        "Unable to get a response. Please try again."
      );
    } finally {
      setSending(false);
    }
  };

  const handleSuggestedQuestion = (question) => {
    setInput(question);
  };

  const handleClearConversation = () => {
    setMessages([]);
    setError("");
  };

  return (
    <div className="assistant-page">
      <section className="assistant-page-header">
        <div>
          <span className="assistant-eyebrow">
            FINANCE INTELLIGENCE
          </span>

          <h1>{assistantWelcome.title}</h1>

          <p>{assistantWelcome.description}</p>
        </div>

        <div className="assistant-status">
          <span className="assistant-status-dot" />
          READY
        </div>
      </section>

      <section className="assistant-workspace">
        <aside className="assistant-sidebar">
          <div className="assistant-sidebar-section">
            <span className="assistant-sidebar-title">
              CAPABILITIES
            </span>

            <div className="assistant-capability">
              <span>01</span>
              <div>
                <strong>Financial Q&A</strong>
                <p>Ask questions about finance data.</p>
              </div>
            </div>

            <div className="assistant-capability">
              <span>02</span>
              <div>
                <strong>Document Intelligence</strong>
                <p>Search indexed financial documents.</p>
              </div>
            </div>

            <div className="assistant-capability">
              <span>03</span>
              <div>
                <strong>Controlled Analysis</strong>
                <p>Analyze approved finance information.</p>
              </div>
            </div>
          </div>

          <div className="assistant-sidebar-section assistant-suggestions">
            <span className="assistant-sidebar-title">
              SUGGESTED QUESTIONS
            </span>

            {assistantSuggestedQuestions.map(
              (question) => (
                <button
                  type="button"
                  key={question}
                  onClick={() =>
                    handleSuggestedQuestion(question)
                  }
                >
                  {question}
                </button>
              )
            )}
          </div>
        </aside>

        <div className="assistant-chat">
          <div className="assistant-chat-header">
            <div>
              <span className="assistant-chat-label">
                ACTIVE ASSISTANT
              </span>
              <strong>Finance AI</strong>
            </div>

            <button
              type="button"
              className="assistant-clear-button"
              onClick={handleClearConversation}
              disabled={messages.length === 0}
            >
              Clear
            </button>
          </div>

          <div className="assistant-messages">
            {loading ? (
              <div className="assistant-loading">
                <div className="assistant-loading-spinner" />
                <span>
                  Initializing Finance AI...
                </span>
              </div>
            ) : (
              <>
                {messages.length === 0 ? (
                  <div className="assistant-empty">
                    <div className="assistant-empty-icon">
                      ✦
                    </div>

                    <h2>Start a finance conversation</h2>

                    <p>
                      Ask a question or select one of the
                      suggested questions.
                    </p>
                  </div>
                ) : (
                  messages.map((message) => (
                    <AssistantMessage
                      key={message.id}
                      message={message}
                    />
                  ))
                )}

                {sending && (
                  <div className="assistant-typing">
                    <span />
                    <span />
                    <span />
                    <em>Finance AI is thinking...</em>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {error && (
            <div className="assistant-error">
              <span>!</span>
              {error}
            </div>
          )}

          <form
            className="assistant-input-area"
            onSubmit={handleSendMessage}
          >
            <div className="assistant-input-wrapper">
              <textarea
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                placeholder="Ask a finance question..."
                rows={1}
                disabled={sending}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey
                  ) {
                    event.preventDefault();
                    handleSendMessage(event);
                  }
                }}
              />

              <button
                type="submit"
                disabled={!input.trim() || sending}
                aria-label="Send message"
              >
                <span>→</span>
              </button>
            </div>

            <div className="assistant-input-footer">
              <span>
                Finance AI responses will be grounded in
                authorized knowledge sources.
              </span>

              <span>ENTER TO SEND</span>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}

export default Assistant;
