export type UiCopyKey =
  | "nav.home"
  | "nav.help"
  | "nav.hospitals"
  | "nav.shelters"
  | "nav.reports"
  | "nav.settings"
  | "chat"
  | "chat.close"
  | "chat.subtitle"
  | "chat.danger"
  | "chat.hello"
  | "chat.placeholder"
  | "chat.replyLanguage"
  | "sos"
  | "sos.confirmTitle"
  | "sos.confirmBody"
  | "sos.call112"
  | "sos.confirm"
  | "sos.cancel"
  | "sos.sending"
  | "signOut"
  | "language.label"
  | "language.help"
  | "home.title"
  | "home.subtitle"
  | "location.yours"
  | "location.refresh"
  | "weather.title"
  | "traffic.title"
  | "help.tag"
  | "help.title"
  | "help.intro"
  | "help.placeholder"
  | "help.submit"
  | "help.working"
  | "help.mic"
  | "help.protocolNote"
  | "result.yours"
  | "result.reliability"
  | "result.doNow"
  | "result.doNot"
  | "result.seekHelp"
  | "result.questions"
  | "result.questionsHint"
  | "result.callServices"
  | "result.carry"
  | "result.hospitals"
  | "result.openMaps"
  | "hospitals.title"
  | "hospitals.directory"
  | "shelters.title"
  | "reports.title"
  | "reports.unverified"
  | "reports.share"
  | "settings.title"
  | "settings.intro"
  | "settings.profileTag"
  | "settings.review"
  | "settings.email"
  | "settings.fullName"
  | "settings.displayName"
  | "settings.phone"
  | "settings.city"
  | "settings.emergencyTag"
  | "settings.emergencyHelp"
  | "settings.contactName"
  | "settings.contactPhone"
  | "settings.relation"
  | "settings.relationSelect"
  | "settings.relationOther"
  | "settings.relationCustom"
  | "settings.relationHint"
  | "settings.relationError"
  | "settings.rel.son"
  | "settings.rel.daughter"
  | "settings.rel.spouse"
  | "settings.rel.father"
  | "settings.rel.mother"
  | "settings.rel.brother"
  | "settings.rel.sister"
  | "settings.rel.friend"
  | "settings.rel.caregiver"
  | "settings.fixFields"
  | "settings.phoneInvalid"
  | "settings.loading"
  | "settings.save"
  | "settings.saveContinue"
  | "settings.saving"
  | "settings.saved"
  | "settings.alertsTitle"
  | "settings.alertsBody"
  | "settings.alertsButton"
  | "settings.alertsUnsupported"
  | "settings.alertsDenied"
  | "settings.alertsPartial"
  | "settings.alertsRetry"
  | "settings.alertsOk"
  | "settings.alertsFail"
  | "settings.alertsError";

type CopyTable = Record<UiCopyKey, string>;

const en: CopyTable = {
  "nav.home": "Home",
  "nav.help": "Get help",
  "nav.hospitals": "Hospitals",
  "nav.shelters": "Shelters",
  "nav.reports": "Local reports",
  "nav.settings": "Settings",
  chat: "Chat",
  "chat.close": "Close chat",
  "chat.subtitle": "For general questions. Not for urgent emergencies.",
  "chat.danger": "If someone is in danger, use Get help or call 112 / 108.",
  "chat.hello":
    "Hello. I can answer general safety questions. I am not for urgent emergencies. If someone needs help right away, use Get help or call 112 / 108.",
  "chat.placeholder": "Ask a general safety question...",
  "chat.replyLanguage": "Reply language",
  sos: "SOS",
  "sos.confirmTitle": "Confirm SOS",
  "sos.confirmBody":
    "This records an SOS for your account and can SMS your emergency contact with your location. It does not notify 112, police, or ambulance automatically.",
  "sos.call112": "Call 112 now",
  "sos.confirm": "Confirm SOS",
  "sos.cancel": "Cancel",
  "sos.sending": "Sending...",
  signOut: "Sign out",
  "language.label": "App language",
  "language.help": "Menus, chat, and clarifying questions use this. First-aid protocol stays in English.",
  "home.title": "Home",
  "home.subtitle": "Location, weather, and roads nearby",
  "location.yours": "Your location",
  "location.refresh": "Refresh",
  "weather.title": "Weather near you",
  "traffic.title": "Traffic near you",
  "help.tag": "Need help now",
  "help.title": "Get help",
  "help.intro":
    "Say what is happening in your own words. The system restates that, looks up similar incidents, then classifies with rules and models. It does not let the chatbot pick how serious this is. For a life-threatening emergency, call 112 first.",
  "help.placeholder": "What is happening? Speak or type, then go.",
  "help.submit": "Get help",
  "help.working": "Working...",
  "help.mic": "Tap the microphone to speak, or press Enter to send.",
  "help.protocolNote": "Chat and clarifying questions use this language. First-aid protocol stays in English.",
  "result.yours": "Your result",
  "result.reliability": "Reliability",
  "result.doNow": "Do this now",
  "result.doNot": "Do not do this",
  "result.seekHelp": "Seek help immediately if",
  "result.questions": "Answer if you can",
  "result.questionsHint": "These questions can change the next step. Tap one to add it to your description.",
  "result.callServices": "Call these services",
  "result.carry": "Things to carry",
  "result.hospitals": "Nearby hospitals",
  "result.openMaps": "Open maps",
  "hospitals.title": "Hospitals",
  "hospitals.directory": "Directory listing only — not live bed or emergency-department status.",
  "shelters.title": "Shelters",
  "reports.title": "Local reports",
  "reports.unverified": "Community observations only. Treat every report as unverified.",
  "reports.share": "Share an update",
  "settings.title": "Settings",
  "settings.intro": "Keep your emergency contact and how they know you current. SOS can SMS them your location.",
  "settings.profileTag": "You",
  "settings.review": "Your details",
  "settings.email": "Email",
  "settings.fullName": "Full name",
  "settings.displayName": "Display name",
  "settings.phone": "Your phone",
  "settings.city": "City / area",
  "settings.emergencyTag": "Who gets the SOS SMS",
  "settings.emergencyHelp":
    "SOS texts them: “Your son has hit an SOS…” plus your location. Pick how they know you.",
  "settings.contactName": "Their name",
  "settings.contactPhone": "Their phone",
  "settings.relation": "I am their",
  "settings.relationSelect": "Select relation",
  "settings.relationOther": "Other",
  "settings.relationCustom": "Relation in their words",
  "settings.relationHint": "e.g. nephew, roommate",
  "settings.relationError": "Say how they know you (son, daughter, spouse, friend…).",
  "settings.rel.son": "Son",
  "settings.rel.daughter": "Daughter",
  "settings.rel.spouse": "Spouse",
  "settings.rel.father": "Father",
  "settings.rel.mother": "Mother",
  "settings.rel.brother": "Brother",
  "settings.rel.sister": "Sister",
  "settings.rel.friend": "Friend",
  "settings.rel.caregiver": "Caregiver",
  "settings.fixFields": "Fix the highlighted fields before saving.",
  "settings.phoneInvalid": "Enter a valid phone number.",
  "settings.loading": "Loading your profile...",
  "settings.save": "Save profile",
  "settings.saveContinue": "Save and continue",
  "settings.saving": "Saving...",
  "settings.saved": "Saved. SOS can SMS this contact with your location.",
  "settings.alertsTitle": "Device alerts",
  "settings.alertsBody":
    "Optional. Alerts go only to devices you register while signed in. They are not a substitute for 112 / 108.",
  "settings.alertsButton": "Turn on device alerts",
  "settings.alertsUnsupported": "This browser does not support alerts.",
  "settings.alertsDenied":
    "Notifications were not allowed. You can turn them on later in your browser settings.",
  "settings.alertsPartial":
    "Browser push alerts are not configured on this install. SOS can still SMS your emergency contact. You can still call 112.",
  "settings.alertsRetry": "Could not finish setting up device alerts. Please try again.",
  "settings.alertsOk":
    "This device can receive ResQ alerts while you are signed in. This is not 112 and does not notify official emergency services.",
  "settings.alertsFail": "Could not save your alert settings. Please try again in a moment.",
  "settings.alertsError": "Something went wrong while enabling alerts. Please try again.",
};

const hi: CopyTable = {
  ...en,
  "nav.home": "होम",
  "nav.help": "मदद लें",
  "nav.hospitals": "अस्पताल",
  "nav.shelters": "आश्रय",
  "nav.reports": "स्थानीय रिपोर्ट",
  "nav.settings": "सेटिंग्स",
  chat: "चैट",
  "chat.close": "चैट बंद करें",
  "chat.subtitle": "सामान्य सवालों के लिए। आपातकाल के लिए नहीं।",
  "chat.danger": "अगर कोई खतरे में है, मदद लें पर जाएँ या 112 / 108 पर कॉल करें।",
  "chat.hello":
    "नमस्ते। मैं सामान्य सुरक्षा सवालों के जवाब दे सकता हूँ। यह आपातकाल के लिए नहीं है। तुरंत मदद चाहिए तो मदद लें इस्तेमाल करें या 112 / 108 पर कॉल करें।",
  "chat.placeholder": "एक सामान्य सुरक्षा सवाल पूछें...",
  "chat.replyLanguage": "जवाब की भाषा",
  sos: "SOS",
  "sos.confirmTitle": "SOS पुष्टि करें",
  "sos.confirmBody":
    "यह आपके खाते के लिए SOS दर्ज करता है और आपका स्थान आपातकालीन संपर्क को SMS कर सकता है। यह 112, पुलिस या एम्बुलेंस को अपने आप सूचना नहीं देता।",
  "sos.call112": "अभी 112 पर कॉल करें",
  "sos.confirm": "SOS पुष्टि करें",
  "sos.cancel": "रद्द करें",
  "sos.sending": "भेजा जा रहा है...",
  signOut: "साइन आउट",
  "language.label": "ऐप भाषा",
  "language.help": "मेनू, चैट और सवाल इसी भाषा में। प्राथमिक उपचार प्रोटोकॉल अंग्रेज़ी में रहता है।",
  "home.title": "होम",
  "home.subtitle": "आपकी लोकेशन, मौसम और आसपास की सड़कें",
  "location.yours": "आपकी लोकेशन",
  "location.refresh": "रिफ्रेश",
  "weather.title": "आपके पास का मौसम",
  "traffic.title": "आपके पास का ट्रैफ़िक",
  "help.tag": "अभी मदद चाहिए",
  "help.title": "मदद लें",
  "help.intro":
    "अपने शब्दों में बताएँ क्या हो रहा है। सिस्टम उसे दोहराता है, मिलते-जुलते मामले देखता है, फिर नियम और मॉडल से वर्गीकृत करता है। गंभीरता चैटबॉट तय नहीं करता। जानलेवा आपातकाल में पहले 112 पर कॉल करें।",
  "help.placeholder": "क्या हो रहा है? बोलें या लिखें, फिर भेजें।",
  "help.submit": "मदद लें",
  "help.working": "काम हो रहा है...",
  "help.mic": "माइक दबाकर बोलें, या Enter दबाकर भेजें।",
  "help.protocolNote": "चैट और सवाल इसी भाषा में। प्राथमिक उपचार प्रोटोकॉल अंग्रेज़ी में रहता है।",
  "result.yours": "आपका परिणाम",
  "result.reliability": "विश्वसनीयता",
  "result.doNow": "अभी यह करें",
  "result.doNot": "यह न करें",
  "result.seekHelp": "तुरंत मदद लें अगर",
  "result.questions": "अगर बता सकें",
  "result.questionsHint": "ये सवाल अगला कदम बदल सकते हैं। टैप करके विवरण में जोड़ें।",
  "result.callServices": "इन नंबरों पर कॉल करें",
  "result.carry": "साथ ले जाएँ",
  "result.hospitals": "नज़दीकी अस्पताल",
  "result.openMaps": "मैप खोलें",
  "hospitals.title": "अस्पताल",
  "hospitals.directory": "केवल डायरेक्टरी — लाइव बेड या इमरजेंसी स्टेटस नहीं।",
  "shelters.title": "आश्रय",
  "reports.title": "स्थानीय रिपोर्ट",
  "reports.unverified": "समुदाय की जानकारी। हर रिपोर्ट को असत्यापित मानें।",
  "reports.share": "अपडेट साझा करें",
  "settings.title": "सेटिंग्स",
  "settings.intro": "आपातकालीन संपर्क और संबंध अपडेट रखें। SOS उन्हें स्थान वाला SMS भेज सकता है।",
  "settings.profileTag": "आप",
  "settings.review": "आपकी जानकारी",
  "settings.email": "ईमेल",
  "settings.fullName": "पूरा नाम",
  "settings.displayName": "दिखने वाला नाम",
  "settings.phone": "आपका फ़ोन",
  "settings.city": "शहर / इलाका",
  "settings.emergencyTag": "SOS SMS किसे जाएगा",
  "settings.emergencyHelp":
    "SOS उन्हें लिखेगा: “Your son has hit an SOS…” और आपका स्थान। चुनें वे आपको कैसे जानते हैं।",
  "settings.contactName": "उनका नाम",
  "settings.contactPhone": "उनका फ़ोन",
  "settings.relation": "मैं हूँ उनका",
  "settings.relationSelect": "रिश्ता चुनें",
  "settings.relationOther": "अन्य",
  "settings.relationCustom": "उनके शब्दों में रिश्ता",
  "settings.relationHint": "जैसे भतीजा, रूममेट",
  "settings.relationError": "बताएँ वे आपको कैसे जानते हैं (son, daughter, spouse, friend…)।",
  "settings.rel.son": "बेटा (son)",
  "settings.rel.daughter": "बेटी (daughter)",
  "settings.rel.spouse": "पति/पत्नी (spouse)",
  "settings.rel.father": "पिता (father)",
  "settings.rel.mother": "माता (mother)",
  "settings.rel.brother": "भाई (brother)",
  "settings.rel.sister": "बहन (sister)",
  "settings.rel.friend": "दोस्त (friend)",
  "settings.rel.caregiver": "देखभाल करने वाले (caregiver)",
  "settings.fixFields": "सेव करने से पहले चिह्नित फ़ील्ड ठीक करें।",
  "settings.phoneInvalid": "सही फ़ोन नंबर डालें।",
  "settings.loading": "प्रोफ़ाइल लोड हो रही है...",
  "settings.save": "प्रोफ़ाइल सेव करें",
  "settings.saveContinue": "सेव करें और आगे बढ़ें",
  "settings.saving": "सेव हो रहा है...",
  "settings.saved": "सेव हो गया। SOS इस नंबर पर स्थान वाला SMS भेज सकता है।",
  "settings.alertsTitle": "डिवाइस अलर्ट",
  "settings.alertsBody":
    "वैकल्पिक। अलर्ट केवल आपके साइन-इन डिवाइस पर जाते हैं। यह 112 / 108 की जगह नहीं है।",
  "settings.alertsButton": "डिवाइस अलर्ट चालू करें",
};

const hinglish: CopyTable = {
  ...en,
  "nav.home": "Home",
  "nav.help": "Help lo",
  "nav.hospitals": "Hospitals",
  "nav.shelters": "Shelters",
  "nav.reports": "Local reports",
  "nav.settings": "Settings",
  chat: "Chat",
  "chat.close": "Chat band karo",
  "chat.subtitle": "General sawaal ke liye. Emergency ke liye nahi.",
  "chat.danger": "Agar koi danger mein hai, Help lo use karo ya 112 / 108 call karo.",
  "chat.hello":
    "Hello. Main general safety sawaal ka jawab de sakta hoon. Urgent emergency ke liye nahi hoon. Turant help chahiye to Help lo use karo ya 112 / 108 call karo.",
  "chat.placeholder": "Ek general safety sawaal poocho...",
  "chat.replyLanguage": "Reply language",
  sos: "SOS",
  "sos.confirmTitle": "SOS confirm karo",
  "sos.confirmBody":
    "Yeh aapke account ke liye SOS record karta hai aur emergency contact ko location wala SMS bhej sakta hai. Yeh 112, police ya ambulance ko automatically notify nahi karta.",
  "sos.call112": "Abhi 112 call karo",
  "sos.confirm": "SOS confirm karo",
  "sos.cancel": "Cancel",
  "sos.sending": "Bhej rahe hain...",
  signOut: "Sign out",
  "language.label": "App language",
  "language.help": "Menus, chat aur sawaal is language mein. First-aid protocol English mein hi rehta hai.",
  "home.title": "Home",
  "home.subtitle": "Location, mausam, aur nearby roads",
  "location.yours": "Aapki location",
  "location.refresh": "Refresh",
  "weather.title": "Aapke paas ka weather",
  "traffic.title": "Aapke paas ka traffic",
  "help.tag": "Abhi help chahiye",
  "help.title": "Help lo",
  "help.intro":
    "Apne words mein batao kya ho raha hai. System usko restates karta hai, similar incidents dekhta hai, phir rules aur models se classify karta hai. Seriousness chatbot decide nahi karta. Life-threatening emergency ho to pehle 112 call karo.",
  "help.placeholder": "Kya ho raha hai? Bolo ya type karo, phir bhejo.",
  "help.submit": "Help lo",
  "help.working": "Kaam ho raha hai...",
  "help.mic": "Mic tap karke bolo, ya Enter daba ke bhejo.",
  "help.protocolNote": "Chat aur clarifying questions is language mein. First-aid protocol English mein rehta hai.",
  "result.yours": "Aapka result",
  "result.reliability": "Reliability",
  "result.doNow": "Abhi yeh karo",
  "result.doNot": "Yeh mat karo",
  "result.seekHelp": "Turant help lo agar",
  "result.questions": "Agar bata sako",
  "result.questionsHint": "Yeh sawaal agla step change kar sakte hain. Tap karke description mein add karo.",
  "result.callServices": "In numbers pe call karo",
  "result.carry": "Saath le jao",
  "result.hospitals": "Nearby hospitals",
  "result.openMaps": "Maps kholo",
  "hospitals.title": "Hospitals",
  "hospitals.directory": "Sirf directory listing — live bed ya ED status nahi.",
  "shelters.title": "Shelters",
  "reports.title": "Local reports",
  "reports.unverified": "Community observations. Har report unverified maano.",
  "reports.share": "Update share karo",
  "settings.title": "Settings",
  "settings.intro": "Emergency contact aur relation update rakho. SOS unhe location wala SMS bhej sakta hai.",
  "settings.profileTag": "Aap",
  "settings.review": "Aapki details",
  "settings.email": "Email",
  "settings.fullName": "Poora naam",
  "settings.displayName": "Display name",
  "settings.phone": "Aapka phone",
  "settings.city": "City / area",
  "settings.emergencyTag": "SOS SMS kisko jayega",
  "settings.emergencyHelp":
    "SOS unhe text karega: “Your son has hit an SOS…” aur aapki location. Choose karo wo aapko kaise jaante hain.",
  "settings.contactName": "Unka naam",
  "settings.contactPhone": "Unka phone",
  "settings.relation": "Main hoon unka",
  "settings.relationSelect": "Relation choose karo",
  "settings.relationOther": "Other",
  "settings.relationCustom": "Unke words mein relation",
  "settings.relationHint": "jaise nephew, roommate",
  "settings.relationError": "Batao wo aapko kaise jaante hain (son, daughter, spouse, friend…).",
  "settings.rel.son": "Beta (son)",
  "settings.rel.daughter": "Beti (daughter)",
  "settings.rel.spouse": "Spouse",
  "settings.rel.father": "Papa (father)",
  "settings.rel.mother": "Mummy (mother)",
  "settings.rel.brother": "Bhai (brother)",
  "settings.rel.sister": "Behen (sister)",
  "settings.rel.friend": "Friend",
  "settings.rel.caregiver": "Caregiver",
  "settings.fixFields": "Save se pehle highlighted fields theek karo.",
  "settings.phoneInvalid": "Sahi phone number daalo.",
  "settings.loading": "Profile load ho rahi hai...",
  "settings.save": "Profile save karo",
  "settings.saveContinue": "Save karke aage badho",
  "settings.saving": "Save ho raha hai...",
  "settings.saved": "Save ho gaya. SOS is contact ko location wala SMS bhej sakta hai.",
  "settings.alertsTitle": "Device alerts",
  "settings.alertsBody":
    "Optional. Alerts sirf aapke signed-in devices pe jaate hain. Yeh 112 / 108 ki jagah nahi hai.",
  "settings.alertsButton": "Device alerts on karo",
  "settings.alertsPartial":
    "Is install pe browser push alerts set nahi hain. SOS phir bhi emergency contact ko SMS bhej sakta hai. 112 call kar sakte ho.",
};

const te: CopyTable = {
  ...en,
  "nav.home": "హోమ్",
  "nav.help": "సహాయం",
  "nav.hospitals": "ఆసుపత్రులు",
  "nav.shelters": "ఆశ్రయాలు",
  "nav.reports": "స్థానిక నివేదికలు",
  "nav.settings": "సెట్టింగ్స్",
  chat: "చాట్",
  "chat.close": "చాట్ మూసివేయి",
  "chat.subtitle": "సాధారణ ప్రశ్నలకు. అత్యవసర పరిస్థితికి కాదు.",
  "chat.danger": "ఎవరైనా ప్రమాదంలో ఉంటే సహాయం వాడండి లేదా 112 / 108కి కాల్ చేయండి.",
  "chat.hello":
    "నమస్కారం. సాధారణ భద్రత ప్రశ్నలకు సమాధానం ఇస్తాను. ఇది అత్యవసర సేవ కాదు. వెంటనే సహాయం కావాలంటే సహాయం వాడండి లేదా 112 / 108కి కాల్ చేయండి.",
  "chat.placeholder": "సాధారణ భద్రత ప్రశ్న అడగండి...",
  "chat.replyLanguage": "సమాధాన భాష",
  sos: "SOS",
  "sos.confirmTitle": "SOS నిర్ధారించండి",
  "sos.confirmBody":
    "ఇది మీ ఖాతాకు SOS నమోదు చేసి మీ స్థానాన్ని అత్యవసర సంప్రదింపుకు SMS పంపవచ్చు. ఇది 112, పోలీసు లేదా అంబులెన్స్‌కు స్వయంగా సమాచారం ఇవ్వదు.",
  "sos.call112": "ఇప్పుడు 112కి కాల్ చేయండి",
  "sos.confirm": "SOS నిర్ధారించండి",
  "sos.cancel": "రద్దు",
  "sos.sending": "పంపుతోంది...",
  signOut: "సైన్ అవుట్",
  "language.label": "యాప్ భాష",
  "language.help": "మెనూలు, చాట్, ప్రశ్నలు ఈ భాషలో. ప్రథమ చికిత్స ప్రోటోకాల్ ఇంగ్లీష్‌లోనే ఉంటుంది.",
  "home.title": "హోమ్",
  "home.subtitle": "మీ స్థానం, వాతావరణం, సమీప రోడ్లు",
  "location.yours": "మీ స్థానం",
  "location.refresh": "రిఫ్రెష్",
  "weather.title": "మీ దగ్గర వాతావరణం",
  "traffic.title": "మీ దగ్గర ట్రాఫిక్",
  "help.tag": "ఇప్పుడు సహాయం కావాలి",
  "help.title": "సహాయం",
  "help.intro":
    "ఏమి జరుగుతోందో మీ మాటల్లో చెప్పండి. సిస్టమ్ దాన్ని మళ్లీ చెబుతుంది, సారూప్య సంఘటనలు చూసి, నియమాలు మరియు మోడల్స్‌తో వర్గీకరిస్తుంది. తీవ్రతను చాట్‌బాట్ నిర్ణయించదు. ప్రాణాపాయ పరిస్థితిలో ముందుగా 112కి కాల్ చేయండి.",
  "help.placeholder": "ఏమి జరుగుతోంది? మాట్లాడండి లేదా టైప్ చేసి పంపండి.",
  "help.submit": "సహాయం",
  "help.working": "పని జరుగుతోంది...",
  "help.mic": "మైక్ నొక్కి మాట్లాడండి, లేదా Enter నొక్కి పంపండి.",
  "help.protocolNote": "చాట్ మరియు ప్రశ్నలు ఈ భాషలో. ప్రథమ చికిత్స ప్రోటోకాల్ ఇంగ్లీష్‌లోనే ఉంటుంది.",
  "result.yours": "మీ ఫలితం",
  "result.reliability": "విశ్వసనీయత",
  "result.doNow": "ఇప్పుడు ఇది చేయండి",
  "result.doNot": "ఇది చేయవద్దు",
  "result.seekHelp": "వెంటనే సహాయం తీసుకోండి ఒకవేళ",
  "result.questions": "చెప్పగలిగితే",
  "result.questionsHint": "ఈ ప్రశ్నలు తర్వాతి అడుగును మార్చవచ్చు. ట్యాప్ చేసి వివరణలో చేర్చండి.",
  "result.callServices": "ఈ నంబర్లకు కాల్ చేయండి",
  "result.carry": "తీసుకెళ్లండి",
  "result.hospitals": "సమీప ఆసుపత్రులు",
  "result.openMaps": "మ్యాప్ తెరవండి",
  "hospitals.title": "ఆసుపత్రులు",
  "hospitals.directory": "డైరెక్టరీ మాత్రమే — లైవ్ బెడ్ లేదా ఎమర్జెన్సీ స్థితి కాదు.",
  "shelters.title": "ఆశ్రయాలు",
  "reports.title": "స్థానిక నివేదికలు",
  "reports.unverified": "సమాజ పరిశీలనలు. ప్రతి నివేదికను ధృవీకరించనిదిగా పరిగణించండి.",
  "reports.share": "అప్‌డేట్ పంచుకోండి",
  "settings.title": "సెట్టింగ్స్",
  "settings.intro": "అత్యవసర సంప్రదింపు మరియు సంబంధం తాజాగా ఉంచండి. SOS వారికి స్థానం SMS పంపవచ్చు.",
  "settings.profileTag": "మీరు",
  "settings.review": "మీ వివరాలు",
  "settings.email": "ఇమెయిల్",
  "settings.fullName": "పూర్తి పేరు",
  "settings.displayName": "డిస్‌ప్లే పేరు",
  "settings.phone": "మీ ఫోన్",
  "settings.city": "నగరం / ప్రాంతం",
  "settings.emergencyTag": "SOS SMS ఎవరికి వెళ్తుంది",
  "settings.emergencyHelp":
    "SOS వారికి పంపుతుంది: “Your son has hit an SOS…” మరియు మీ స్థానం. వారు మిమ్మల్ని ఎలా తెలుసుకుంటారో ఎంచుకోండి.",
  "settings.contactName": "వారి పేరు",
  "settings.contactPhone": "వారి ఫోన్",
  "settings.relation": "నేను వారికి",
  "settings.relationSelect": "సంబంధం ఎంచుకోండి",
  "settings.relationOther": "ఇతరం",
  "settings.relationCustom": "వారి మాటల్లో సంబంధం",
  "settings.relationHint": "ఉదా. మేనల్లుడు, రూమ్‌మేట్",
  "settings.relationError": "వారు మిమ్మల్ని ఎలా తెలుసుకుంటారో చెప్పండి (son, daughter, spouse, friend…).",
  "settings.rel.son": "కొడుకు (son)",
  "settings.rel.daughter": "కూతురు (daughter)",
  "settings.rel.spouse": "జీవిత భాగస్వామి (spouse)",
  "settings.rel.father": "తండ్రి (father)",
  "settings.rel.mother": "తల్లి (mother)",
  "settings.rel.brother": "సోదరుడు (brother)",
  "settings.rel.sister": "సోదరి (sister)",
  "settings.rel.friend": "స్నేహితుడు (friend)",
  "settings.rel.caregiver": "సంరక్షకుడు (caregiver)",
  "settings.fixFields": "సేవ్ చేసే ముందు గుర్తించిన ఫీల్డ్‌లు సరిచేయండి.",
  "settings.phoneInvalid": "సరైన ఫోన్ నంబర్ ఇవ్వండి.",
  "settings.loading": "ప్రొఫైల్ లోడ్ అవుతోంది...",
  "settings.save": "ప్రొఫైల్ సేవ్ చేయండి",
  "settings.saveContinue": "సేవ్ చేసి కొనసాగండి",
  "settings.saving": "సేవ్ అవుతోంది...",
  "settings.saved": "సేవ్ అయింది. SOS ఈ కాంటాక్ట్‌కు స్థానం SMS పంపవచ్చు.",
  "settings.alertsTitle": "డివైస్ అలర్ట్‌లు",
  "settings.alertsBody":
    "ఐచ్ఛికం. అలర్ట్‌లు మీరు సైన్ ఇన్ చేసిన డివైస్‌లకు మాత్రమే. ఇది 112 / 108కి ప్రత్యామ్నాయం కాదు.",
  "settings.alertsButton": "డివైస్ అలర్ట్‌లు ఆన్ చేయండి",
};

const ur: CopyTable = {
  ...en,
  "nav.home": "ہوم",
  "nav.help": "مدد لیں",
  "nav.hospitals": "ہسپتال",
  "nav.shelters": "پناہ گاہیں",
  "nav.reports": "مقامی رپورٹس",
  "nav.settings": "ترتیبات",
  chat: "چیٹ",
  "chat.close": "چیٹ بند کریں",
  "chat.subtitle": "عام سوالات کے لیے۔ ہنگامی صورتحال کے لیے نہیں۔",
  "chat.danger": "اگر کوئی خطرے میں ہے تو مدد لیں استعمال کریں یا 112 / 108 پر کال کریں۔",
  "chat.hello":
    "السلام علیکم۔ میں عام حفاظتی سوالات کے جواب دے سکتا ہوں۔ یہ ہنگامی خدمت نہیں۔ فوری مدد چاہیے تو مدد لیں استعمال کریں یا 112 / 108 پر کال کریں۔",
  "chat.placeholder": "ایک عام حفاظتی سوال پوچھیں...",
  "chat.replyLanguage": "جواب کی زبان",
  sos: "SOS",
  "sos.confirmTitle": "SOS کی تصدیق کریں",
  "sos.confirmBody":
    "یہ آپ کے اکاؤنٹ کے لیے SOS درج کرتا ہے اور لوکیشن والا SMS ایمرجنسی رابطے کو بھیج سکتا ہے۔ یہ 112، پولیس یا ایمبولینس کو خود بخود اطلاع نہیں دیتا۔",
  "sos.call112": "ابھی 112 پر کال کریں",
  "sos.confirm": "SOS تصدیق کریں",
  "sos.cancel": "منسوخ",
  "sos.sending": "بھیجا جا رہا ہے...",
  signOut: "سائن آؤٹ",
  "language.label": "ایپ کی زبان",
  "language.help": "مینو، چیٹ اور سوالات اسی زبان میں۔ فرسٹ ایڈ پروٹوکول انگریزی میں رہتا ہے۔",
  "home.title": "ہوم",
  "home.subtitle": "آپ کا مقام، موسم اور قریبی سڑکیں",
  "location.yours": "آپ کا مقام",
  "location.refresh": "ریفریش",
  "weather.title": "آپ کے قریب موسم",
  "traffic.title": "آپ کے قریب ٹریفک",
  "help.tag": "ابھی مدد چاہیے",
  "help.title": "مدد لیں",
  "help.intro":
    "اپنے الفاظ میں بتائیں کیا ہو رہا ہے۔ نظام اسے دہراتا ہے، ملتے جلتے واقعات دیکھتا ہے، پھر قواعد اور ماڈلز سے درجہ بندی کرتا ہے۔ شدت چیٹ بوٹ طے نہیں کرتا۔ جان لیوا ایمرجنسی میں پہلے 112 پر کال کریں۔",
  "help.placeholder": "کیا ہو رہا ہے؟ بولیں یا لکھیں، پھر بھیجیں۔",
  "help.submit": "مدد لیں",
  "help.working": "کام ہو رہا ہے...",
  "help.mic": "مائیک دبا کر بولیں، یا Enter دبا کر بھیجیں۔",
  "help.protocolNote": "چیٹ اور سوالات اسی زبان میں۔ فرسٹ ایڈ پروٹوکول انگریزی میں رہتا ہے۔",
  "result.yours": "آپ کا نتیجہ",
  "result.reliability": "قابل اعتماد",
  "result.doNow": "اب یہ کریں",
  "result.doNot": "یہ نہ کریں",
  "result.seekHelp": "فوری مدد لیں اگر",
  "result.questions": "اگر بتا سکیں",
  "result.questionsHint": "یہ سوالات اگلا قدم بدل سکتے ہیں۔ ٹیپ کر کے تفصیل میں شامل کریں۔",
  "result.callServices": "ان نمبروں پر کال کریں",
  "result.carry": "ساتھ لے جائیں",
  "result.hospitals": "قریبی ہسپتال",
  "result.openMaps": "نقشہ کھولیں",
  "hospitals.title": "ہسپتال",
  "hospitals.directory": "صرف ڈائریکٹری — لائیو بیڈ یا ایمرجنسی سٹیٹس نہیں۔",
  "shelters.title": "پناہ گاہیں",
  "reports.title": "مقامی رپورٹس",
  "reports.unverified": "کمیونٹی مشاہدات۔ ہر رپورٹ کو غیر تصدیق شدہ سمجھیں۔",
  "reports.share": "اپ ڈیٹ شیئر کریں",
  "settings.title": "ترتیبات",
  "settings.intro": "ایمرجنسی رابطہ اور رشتہ تازہ رکھیں۔ SOS انہیں لوکیشن والا SMS بھیج سکتا ہے۔",
  "settings.profileTag": "آپ",
  "settings.review": "آپ کی تفصیل",
  "settings.email": "ای میل",
  "settings.fullName": "پورا نام",
  "settings.displayName": "ڈسپلے نام",
  "settings.phone": "آپ کا فون",
  "settings.city": "شہر / علاقہ",
  "settings.emergencyTag": "SOS SMS کسے جائے گا",
  "settings.emergencyHelp":
    "SOS انہیں بھیجے گا: “Your son has hit an SOS…” اور آپ کا مقام۔ منتخب کریں وہ آپ کو کیسے جانتے ہیں۔",
  "settings.contactName": "ان کا نام",
  "settings.contactPhone": "ان کا فون",
  "settings.relation": "میں ہوں ان کا",
  "settings.relationSelect": "رشتہ منتخب کریں",
  "settings.relationOther": "دیگر",
  "settings.relationCustom": "ان کے الفاظ میں رشتہ",
  "settings.relationHint": "جیسے بھتیجا، روم میٹ",
  "settings.relationError": "بتائیں وہ آپ کو کیسے جانتے ہیں (son, daughter, spouse, friend…).",
  "settings.rel.son": "بیٹا (son)",
  "settings.rel.daughter": "بیٹی (daughter)",
  "settings.rel.spouse": "شریک حیات (spouse)",
  "settings.rel.father": "والد (father)",
  "settings.rel.mother": "والدہ (mother)",
  "settings.rel.brother": "بھائی (brother)",
  "settings.rel.sister": "بہن (sister)",
  "settings.rel.friend": "دوست (friend)",
  "settings.rel.caregiver": "نگہداشت کرنے والے (caregiver)",
  "settings.fixFields": "محفوظ کرنے سے پہلے نشان زد فیلڈ ٹھیک کریں۔",
  "settings.phoneInvalid": "درست فون نمبر درج کریں۔",
  "settings.loading": "پروفائل لوڈ ہو رہی ہے...",
  "settings.save": "پروفائل محفوظ کریں",
  "settings.saveContinue": "محفوظ کریں اور آگے بڑھیں",
  "settings.saving": "محفوظ ہو رہا ہے...",
  "settings.saved": "محفوظ ہو گیا۔ SOS اس رابطے کو لوکیشن والا SMS بھیج سکتا ہے۔",
  "settings.alertsTitle": "ڈیوائس الرٹس",
  "settings.alertsBody":
    "اختیاری۔ الرٹس صرف آپ کے سائن ان ڈیوائسز پر جاتے ہیں۔ یہ 112 / 108 کا متبادل نہیں۔",
  "settings.alertsButton": "ڈیوائس الرٹس آن کریں",
};

const TABLES: Record<string, CopyTable> = {
  English: en,
  Hindi: hi,
  Hinglish: hinglish,
  Telugu: te,
  Urdu: ur,
};

export function translate(language: string, key: UiCopyKey): string {
  return TABLES[language]?.[key] ?? en[key];
}
