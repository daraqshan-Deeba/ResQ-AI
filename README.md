# ResQ-AI
An AI-powered emergency response and disaster management platform providing real-time risk assessment, weather monitoring, AI-powered emergency assistance, nearby resources, community reports, and SOS location capture.


# 🚨 ResQ AI — Emergency Response & Disaster Management Platform

ResQ AI is an AI-powered emergency response and disaster management platform designed to help people make faster and safer decisions during emergencies and natural disasters.

The platform combines AI-powered emergency assistance, real-time weather monitoring, risk assessment, nearby emergency resources, community reports, and SOS location support into one unified system.

---

## 🌟 Overview

During emergencies, people often need immediate access to reliable information, nearby resources, and clear guidance. ResQ AI aims to simplify this process by providing multiple emergency support features through a single platform.

The system provides:

- 🤖 AI-powered emergency assistance
- 🚨 Emergency situation assessment
- 🌦️ Live weather monitoring
- 📊 Risk score calculation
- 🏥 Nearby hospital discovery
- 🏠 Emergency shelter information
- 👥 Community disaster reports
- 🆘 SOS location support
- 🔔 Push notification support

ResQ AI is designed as a prototype demonstrating how AI, real-time data, mapping services, cloud services, and web technologies can work together to support emergency response.

---

## ✨ Key Features

### 🤖 AI Emergency Assistant

The ResQ AI assistant allows users to describe their emergency situation and receive AI-generated guidance.

Users can explain what is happening, and the system can provide information such as:

- What may be happening
- Immediate first-aid guidance
- Things to avoid
- Emergency services to contact
- Things to carry
- Nearby help suggestions

The AI assistant is powered by a backend AI service and is designed to provide quick emergency guidance.

> ⚠️ AI-generated responses should not replace professional emergency services or medical advice.

---

### 🚨 Emergency Assessment

Users can quickly describe an emergency situation or select from predefined emergency scenarios.

Example scenarios include:

- Flooding
- Electrical hazards
- Injuries
- Snake bites

The system processes the situation and provides structured emergency guidance.

Voice input is also supported through the browser's built-in Web Speech API where available.

---

### 🌦️ Weather Monitoring

ResQ AI retrieves live weather information and displays relevant conditions on the emergency dashboard.

The dashboard can show:

- Current temperature
- Weather conditions
- Rainfall intensity
- Weather alerts

Weather information is used as one of the inputs for the platform's risk assessment system.

---

### 📊 Emergency Risk Assessment

The platform calculates a risk score based on available weather information and a simplified drainage capacity factor.

The risk level is categorized as:

- 🟢 Safe
- 🟡 Watch
- 🟠 Warning
- 🔴 Critical

The risk score is currently a heuristic prototype and should not be considered an official flood prediction or disaster warning system.

---

### 🏥 Nearby Hospitals

The platform can retrieve nearby hospitals using mapping and location services.

Hospital information may include:

- Hospital name
- Address
- Nearby location information

The hospital data is intended to help users quickly identify nearby medical facilities during emergencies.

---

### 🏠 Emergency Shelters

ResQ AI provides information about emergency shelters stored in the application's database.

Shelter information can include:

- Shelter name
- Capacity
- Current occupancy

Shelter and occupancy information is manually maintained and should be considered demonstration data unless connected to an official real-time data source.

---

### 👥 Community Reports

Users can submit reports about emergency situations in their area.

Community reports may include:

- Area
- Description of the situation
- Verification status
- Time of submission

This feature is designed to demonstrate how community-generated information can contribute to emergency awareness.

---

### 🆘 SOS Location Support

The SOS feature uses the browser's Geolocation API to request the user's current latitude and longitude.

When the user confirms an SOS request:

1. The browser asks for location permission.
2. The user's current coordinates are obtained.
3. The coordinates are sent to the ResQ AI backend.
4. The backend processes the SOS request.

The current prototype demonstrates the technical flow of capturing and transmitting the user's location.

> ⚠️ The current prototype does not automatically send the location to emergency services, police, hospitals, or a personal emergency contact unless such functionality is separately configured and implemented.

---

### 🔔 Push Notifications

The platform includes support for browser push notifications using Firebase Cloud Messaging.

Users can enable push notifications from the Settings page.

The system can register a browser device token with the backend and use Firebase services for notification delivery.

---

## 🏗️ System Architecture

```text
                         ┌──────────────────────┐
                         │      ResQ AI User    │
                         │      Web Browser     │
                         └──────────┬───────────┘
                                    │
                                    │ HTTP Requests
                                    ▼
                         ┌──────────────────────┐
                         │    HTML / CSS / JS   │
                         │      Frontend        │
                         └──────────┬───────────┘
                                    │
                                    │ REST API
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │       Backend        │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌────────────┐       ┌──────────────┐      ┌──────────────┐
       │ AI Service │       │ Weather API  │      │ Maps Service │
       └────────────┘       └──────────────┘      └──────────────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Firebase / Database  │
                         │ & Notification Data  │
                         └──────────────────────┘
```
---

## 🎥 Project Demo

Watch the ResQ AI demonstration video to see the platform in action, including the AI emergency assistant, emergency assessment, weather and risk monitoring, nearby hospitals, emergency shelters, community reports, and SOS location capture.

▶️ **[Watch the ResQ AI Demo Video](https://drive.google.com/file/d/1jJbfOfn6eXi7nX2v4HG8RFXsgCtsK_vf/view?usp=sharing)**

> The demo video is hosted on Google Drive.

## 🛠️ Technology Stack

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Browser Geolocation API
- Firebase Cloud Messaging

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- HTTPX

### External Services

- AI API
- OpenWeatherMap API
- Google Places / Maps Services
- Firebase Cloud Messaging
- Firestore
