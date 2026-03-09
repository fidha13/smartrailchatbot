
import { useState, useRef, useEffect } from "react";

function App() {

  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);
  const [isOpen, setIsOpen] = useState(false);

  const chatEndRef = useRef(null);

  const sendMessage = async () => {

    if (!message.trim()) return;

    const userText = message;

    setChat(prev => [...prev, { sender: "user", text: userText }]);
    setMessage("");

    try {

      const response = await fetch(
        "http://localhost:5005/webhooks/rest/webhook",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sender: "user",
            message: userText
          })
        }
      );

      const data = await response.json();

      if (Array.isArray(data)) {

        const botMessages = data.map(msg => ({
          sender: "bot",
          text: msg.text || "",
          buttons: msg.buttons || []
        }));

        setChat(prev => [...prev, ...botMessages]);

      }

    } catch {

      setChat(prev => [
        ...prev,
        { sender: "bot", text: "⚠️ SmartRail server unreachable." }
      ]);

    }

  };


  const handleButtonClick = async (payload, title) => {

    setChat(prev => [...prev, { sender: "user", text: title || payload }]);

    try {

      const response = await fetch(
        "http://localhost:5005/webhooks/rest/webhook",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sender: "user",
            message: payload
          })
        }
      );

      const data = await response.json();

      if (Array.isArray(data)) {

        const botMessages = data.map(msg => ({
          sender: "bot",
          text: msg.text || "",
          buttons: msg.buttons || []
        }));

        setChat(prev => [...prev, ...botMessages]);

      }

    } catch {

      setChat(prev => [
        ...prev,
        { sender: "bot", text: "⚠️ Server error." }
      ]);

    }

  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);



  /* NEW FUNCTION ADDED */
  const handleClose = () => {
    setIsOpen(false);
    setChat([]);     
    setMessage("");  
  };



  return (

    <div>

      {isOpen && (

        <div style={styles.chatContainer}>

          <div style={styles.header}>

            <img src="/chatbot.png" style={styles.headerIcon} />

            SmartRail Assistant

            <span
              style={styles.closeBtn}
              onClick={handleClose}
            >
              ✕
            </span>

          </div>


          <div style={styles.chatBox}>

            {chat.map((msg, index) => (

              <div
                key={index}
                style={
                  msg.sender === "user"
                    ? styles.userContainer
                    : styles.botContainer
                }
              >

                <div
                  style={
                    msg.sender === "user"
                      ? styles.userMessage
                      : styles.botMessage
                  }
                >

                  {msg.text}

                  {msg.buttons && msg.buttons.length > 0 && (

                    <div style={styles.buttonContainer}>

                      {msg.buttons.map((btn, i) => (

                        <button
                          key={i}
                          style={styles.optionButton}
                          onClick={() =>
                            handleButtonClick(btn.payload, btn.title)
                          }
                        >
                          {btn.title}
                        </button>

                      ))}

                    </div>

                  )}

                </div>

              </div>

            ))}

            <div ref={chatEndRef} />

          </div>


          <div style={styles.inputArea}>

            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Type your message..."
              style={styles.input}
              onKeyDown={(e) => {
                if (e.key === "Enter") sendMessage();
              }}
            />

            <button onClick={sendMessage} style={styles.sendButton}>
              Send
            </button>

          </div>

        </div>

      )}


      {!isOpen && (

        <div
          style={styles.mascotButton}
          onClick={() => setIsOpen(true)}
        >

          <img src="/chatbot.png" style={styles.mascotImage} />

        </div>

      )}

    </div>

  );

}


const styles = {

  mascotButton: {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    cursor: "pointer",
    zIndex: 9999
  },

  mascotImage: {
    width: "90px",
    height: "90px"
  },


  chatContainer: {
    position: "fixed",
    bottom: "20px",
    right: "5px",
    width: "420px",
    height: "600px",
    backgroundColor: "#111827",
    borderRadius: "16px",
    display: "flex",
    flexDirection: "column",
    boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
    overflow: "hidden"
  },


  header: {
    padding: "18px",
    background: "#2563eb",
    color: "white",
    fontWeight: "bold",
    fontSize: "18px",
    display: "flex",
    alignItems: "center",
    gap: "10px"
  },


  headerIcon: {
    width: "40px",
    height: "40px"
  },


  closeBtn: {
    marginLeft: "auto",
    cursor: "pointer",
    fontSize: "18px"
  },


  chatBox: {
    flex: 1,
    padding: "15px",
    overflowY: "auto"
  },


  userContainer: {
    display: "flex",
    justifyContent: "flex-end",
    marginBottom: "10px"
  },


  botContainer: {
    display: "flex",
    justifyContent: "flex-start",
    marginBottom: "10px"
  },


  userMessage: {
    background: "#2563eb",
    color: "white",
    padding: "12px 16px",
    borderRadius: "16px",
    maxWidth: "75%",
    fontSize: "15px",
    lineHeight: "1.6"
  },


  botMessage: {
    background: "#1f2937",
    color: "white",
    padding: "12px 16px",
    borderRadius: "16px",
    maxWidth: "75%",
    fontSize: "15px",
    lineHeight: "1.6"
  },


  buttonContainer: {
    marginTop: "8px",
    display: "flex",
    flexWrap: "wrap",
    gap: "6px"
  },


  optionButton: {
    padding: "8px 12px",
    borderRadius: "8px",
    border: "none",
    background: "#2563eb",
    color: "white",
    fontSize: "13px",
    cursor: "pointer"
  },


  inputArea: {
    display: "flex",
    padding: "10px",
    borderTop: "1px solid #1f2937"
  },


  input: {
    flex: 1,
    padding: "10px",
    borderRadius: "6px",
    border: "1px solid #334155",
    backgroundColor: "#1e293b",
    color: "white"
  },


  sendButton: {
    marginLeft: "8px",
    padding: "10px 16px",
    borderRadius: "6px",
    border: "none",
    background: "#2563eb",
    color: "white",
    cursor: "pointer"
  }

};

export default App;