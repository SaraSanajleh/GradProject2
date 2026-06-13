#  MedCompass: Intelligent Arabic Medical Triage System

MedCompass is an AI-powered Arabic medical triage system designed to support the early patient intake process in hospitals and clinics. The system conducts structured symptom-based conversations in Arabic, detects emergency cases, recommends the most appropriate medical department, and assists patients in scheduling appointments.

The project combines Large Language Models (LLMs), Multi-Agent Systems (MAS), and Retrieval-Augmented Generation (RAG) to improve patient routing, reduce waiting times, and support healthcare staff through intelligent automation.

> **Disclaimer:** MedCompass is a triage support system and does not provide medical diagnoses or treatment recommendations.

---

##  Features

- Arabic medical conversations
- Multi-turn symptom collection
- Structured clinical information extraction
- Emergency case detection
- Medical department recommendation
- Confidence and stability-based decision making
- Appointment scheduling and booking
- Automated appointment reminders
- Retrieval-Augmented Generation (RAG)
- Multi-Agent Architecture
- Scenario-based evaluation framework

---

##  System Architecture

The system consists of specialized agents that collaborate through a centralized shared memory.

### Asking Agent
Responsible for interacting with the patient and collecting clinical information through medically relevant follow-up questions.

### Structured Information Agent
Extracts and organizes patient information into structured clinical fields such as:

- Symptoms
- Duration
- Severity
- Associated factors
- Additional notes

### Emergency Agent
Monitors patient information and detects potentially life-threatening conditions.

### Department Agent
Analyzes patient information and recommends the most appropriate clinical department using confidence and stability mechanisms.

### Scheduling Component
Retrieves available appointments and manages booking operations.

### Reminder Component
Automatically sends appointment reminders before scheduled visits.

---

##  Retrieval-Augmented Generation (RAG)

The system employs a dual-layer RAG architecture:

### Primary Medical Knowledge RAG

Used for:

- Medical reasoning
- Follow-up question generation
- Department recommendation

Knowledge base:

- 925 curated medical cases
- Built from trusted medical sources

### Emergency RAG

Used specifically for:

- Emergency detection
- Critical symptom identification

Knowledge base:

- 630 emergency scenarios

---

##  Workflow

```text
Patient Input
      ↓
Arabic Validation
      ↓
Asking Agent
      ↓
Structured Information Agent
      ↓
Emergency Detection
      ↓
Department Prediction
      ↓
Stability Verification
      ↓
Appointment Retrieval
      ↓
Booking Confirmation
      ↓
Reminder Service
```

---

##  Supported Medical Departments

- Neurology
- Cardiology
- Oncology
- Dermatology
- Gastroenterology
- Orthopedics
- Obstetrics & Gynecology
- Ophthalmology
- Urology
- Endocrinology
- Pulmonology
- Pediatrics
- ENT
- Dentistry
- Psychiatry

---

##  Evaluation

The system was evaluated using clinically grounded scenario-based testing.

### Evaluation Settings

- Expert Evaluation
- Automated Agent Evaluation
- Emergency Evaluation

### Evaluation Criteria

- Clinical Relevance
- Question Specificity
- Safety
- Linguistic Quality
- Information Extraction
- Emergency Detection
- Department Selection
- Decision Stability

---

##  Results

| Metric | Score |
|----------|----------|
| Department Selection Accuracy | **96%** |
| Emergency Detection Accuracy | **99%** |

The proposed **Multi-Agent + RAG** architecture consistently outperformed both:

- Single-Agent Baseline
- Multi-Agent without RAG Baseline

---

##  Technologies Used

- Python
- DeepSeek V3.1
- Large Language Models (LLMs)
- Multi-Agent Systems (MAS)
- Retrieval-Augmented Generation (RAG)
- Vector Databases
- Relational Databases
- Prompt Engineering
- Arabic NLP

---

##  Contributions

This project contributes:

1. An intelligent Arabic medical triage system.
2. A multi-agent architecture for clinical workflow management.
3. A dual-layer RAG framework for medical and emergency reasoning.
4. A confidence-based department recommendation mechanism.
5. An end-to-end workflow from symptom collection to appointment booking.
6. A structured evaluation framework for medical triage systems.

---

##  Authors

- Sara Alsanajleh
- Ghada AbuShaqra
- Maian Alabweh

**Department of Computer Science**  
Jordan University of Science and Technology (JUST)  
Irbid, Jordan

---

##  Supervisor

Dr. Rasha Obeidat

---

## 📄 License

This project was developed as a graduation project at Jordan University of Science and Technology (JUST).
