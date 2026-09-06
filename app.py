import os
import json
import streamlit as st
from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai
from streamlit_float import float_init

# 1. PUSLAPIO KONFIGŪRACIJA IR FLOAT INICIALIZAVIMAS (Privalo būti pačiame viršuje)
st.set_page_config(
    page_title="MedStudy Dashboard", 
    page_icon="🩺", 
    layout="wide"
)
float_init()

# Užkrauname .env API raktą (lokaliam naudojimui) ir pritaikome Streamlit debesytos (Cloud) saugyklai
load_dotenv()
api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# Custom CSS tamsiai temai ir burbulo stiliui
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    div[data-testid="stMetric"] {
        background-color: #1e222d;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #2e3440;
    }
    /* Stilius plaukiojančiam popover mygtukui */
    div[data-testid="stPopover"] > button {
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        background-color: #10b981 !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
        font-size: 24px !important;
    }
    div[data-testid="stPopover"] > button:hover {
        transform: scale(1.08);
        background-color: #059669 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SESIJOS DUOMENYS ---
if "cycles" not in st.session_state:
    st.session_state["cycles"] = {
        "Anestezija ir bendroji chirurgija": {
            "text": "",
            "flashcards": [],
            "quiz": [],
            "pairs": [],
            "cheatsheet": "",
            "doctordle": None
        }
    }

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

# --- ŠONINĖ JUOSTA ---
with st.sidebar:
    st.title("🩺 MedStudy Hub")
    st.caption("📍 *Valdyk ir perjunk savo ciklus*")
    st.divider()
    
    cycle_names = list(st.session_state["cycles"].keys())
    selected_cycle = st.selectbox(
        "🎯 Pasirink aktyvų ciklą:", 
        cycle_names,
        key="cycle_selector"
    )
    
    with st.expander("➕ Pridėti naują ciklą"):
        new_cycle_name = st.text_input("Ciklo pavadinimas:", key="new_cycle_input")
        if st.button("Sukurti ciklą", key="create_cycle_btn") and new_cycle_name:
            if new_cycle_name not in st.session_state["cycles"]:
                st.session_state["cycles"][new_cycle_name] = {
                    "text": "", "flashcards": [], "quiz": [], "pairs": [], "cheatsheet": "", "doctordle": None
                }
                st.success(f"Ciklas '{new_cycle_name}' sukurtas!")
                st.rerun()

    st.divider()
    
    st.subheader(f"📥 Skaidrės: {selected_cycle}")
    uploaded_files = st.file_uploader(
        "Įkelk PDF skaidres šiam ciklui", 
        type=["pdf"], 
        accept_multiple_files=True,
        key=f"uploader_{selected_cycle}"
    )
    
    if uploaded_files:
        full_text = ""
        for file in uploaded_files:
            pdf_reader = PdfReader(file)
            for p in pdf_reader.pages:
                txt = p.extract_text()
                if txt:
                    full_text += txt + "\n"
        st.session_state["cycles"][selected_cycle]["text"] = full_text
        st.success("Skaidrės įkeltos!")

    st.divider()
    if st.button("🏠 Grįžti į Dashboard", key="sidebar_home_btn"):
        st.session_state["current_page"] = "Dashboard"
        st.rerun()

current_cycle_data = st.session_state["cycles"][selected_cycle]
has_slides = len(current_cycle_data["text"]) > 0

# --- AI GENERAVIMAS ---
def generate_study_material(slides_text):
    if not client:
        st.error("⚠️ API raktas nerastas. Patikrink `.env` failą arba Streamlit Secrets.")
        return None
        
    prompt = f"""
    Tu esi patyręs medicinos dėstytojas. Išnagrinėk pateiktą skaidrių tekstą ir sugeneruok JSON struktūrą su studijų užduotimis lietuvių kalba.

    Atsakymo formatas privalo būti TIK GRYNAS JSON be jokių papildomų komentarų ar Markdown žymių (be ```json ... ```):
    {{
        "flashcards": [{{"klausimas": "Klausimas...", "atsakymas": "Atsakymas..."}}],
        "quiz": [{{
            "klausimas": "Klausimas...",
            "variantai": ["A) ...", "B) ...", "C) ...", "D) ..."],
            "teisingas": "A) ...",
            "paaiskinimas": "Paaiškinimas..."
        }}],
        "pairs": [{{"kaire": "Sąvoka", "desine": "Apibrėžimas"}}],
        "cheatsheet": "Sutraukta informacija...",
        "doctordle": {{
            "liga": "Diagnozė",
            "uzuoMINOS": ["Užuomina 1", "Užuomina 2", "Užuomina 3", "Užuomina 4"]
        }}
    }}

    Skaidrių tekstas:
    {slides_text[:15000]}
    """
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        clean_json = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Klaida generuojant turinį per AI: {e}")
        return None

# --- DASHBOARD RODYMAS ---
if st.session_state["current_page"] == "Dashboard":
    st.caption(f"AKTYVUS CIKLAS: **{selected_cycle.upper()}**")
    st.title("Išmok medžiagą per praktinius žaidimus ir testus 🎯")
    
    flashcard_count = len(current_cycle_data.get("flashcards", []))
    quiz_count = len(current_cycle_data.get("quiz", []))
    pairs_count = len(current_cycle_data.get("pairs", []))
    
    if has_slides:
        if flashcard_count == 0:
            st.info("💡 Skaidrės įkeltos! Paspausk mygtuką žemiau, kad AI sugeneruotų korteles, testus ir poras.")
            if st.button("✨ Generuoti mokymosi medžiagą su Gemini AI", type="primary"):
                with st.spinner("AI analizuoja skaidres ir kuria užduotis..."):
                    ai_result = generate_study_material(current_cycle_data["text"])
                    if ai_result:
                        current_cycle_data["flashcards"] = ai_result.get("flashcards", [])
                        current_cycle_data["quiz"] = ai_result.get("quiz", [])
                        current_cycle_data["pairs"] = ai_result.get("pairs", [])
                        current_cycle_data["cheatsheet"] = ai_result.get("cheatsheet", "")
                        current_cycle_data["doctordle"] = ai_result.get("doctordle", None)
                        st.success("Mokymosi medžiaga sėkmingai sugeneruota!")
                        st.rerun()
        else:
            st.success("✅ AI medžiaga paruošta mokymuisi!")
    else:
        st.warning("⚠️ Šiam ciklui dar neįkėlei skaidrių. Įkelk PDF failus kairėje juostoje.")

    st.markdown("---")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("KORTELIŲ", str(flashcard_count))
    with col_m2:
        st.metric("VIKTORINOS KLAUSIMŲ", str(quiz_count))
    with col_m3:
        st.metric("PORŲ / DĖLIONIŲ", str(pairs_count))
    with col_m4:
        st.metric("BŪSENA", "Paruošta" if flashcard_count > 0 else "Laukia skaidrių")
        
    st.markdown("---")
    
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        st.subheader("🗂️ Kortelės")
        st.caption("Aktyvus prisiminimas: klausimas ➔ apversk ➔ patikrink atsakymą.")
        if st.button("Mokytis ➔", key="btn_flashcards"):
            st.session_state["current_page"] = "Kortelės"
            st.rerun()
            
    with row1_col2:
        st.subheader("✏️ Viktorina")
        st.caption("Pasirinkimo klausimai su paaiškinimais.")
        if st.button("Testuotis ➔", key="btn_quiz"):
            st.session_state["current_page"] = "Viktorina"
            st.rerun()

    with row1_col3:
        st.subheader("🩺 Doctordle")
        st.caption("Klinikinis žaidimas: atspėk ligą iš užuominų.")
        if st.button("Žaisti ➔", key="btn_doctordle"):
            st.session_state["current_page"] = "Doctordle"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    row2_col1, row2_col2, row2_col3 = st.columns(3)
    with row2_col1:
        st.subheader("🔄 Poros / Dėlionės")
        st.caption("Sudėliok poras: vaistas ↔ dozė, simptomas ↔ liga.")
        if st.button("Dėlioti ➔", key="btn_pairs"):
            st.session_state["current_page"] = "Poros"
            st.rerun()

    with row2_col2:
        st.subheader("📜 Špargalkė")
        st.caption("Sutraukta svarbiausia informacija.")
        if st.button("Skaityti ➔", key="btn_cheat"):
            st.session_state["current_page"] = "Špargalkė"
            st.rerun()

    with row2_col3:
        st.subheader("❓ Mano klausimai")
        st.caption("Išsaugoti klausimai vienoje vietoje.")
        if st.button("Peržiūrėti ➔", key="btn_my_q"):
            st.session_state["current_page"] = "Mano klausimai"
            st.rerun()

else:
    st.button("⬅️ Grįžti į Dashboard", on_click=lambda: st.session_state.update({"current_page": "Dashboard"}))
    st.title(f"{st.session_state['current_page']} — {selected_cycle}")

# --- PLAUKIOJANTIS APVALUS CHAT BURBULAS (STREAMLIT POP-OVER + FLOAT) ---
float_box = st.container()

with float_box:
    with st.popover("💬", help="Gemini AI Dėstytojas"):
        st.markdown("### 💬 Gemini AI Dėstytojas")
        st.caption("Užduok klausimą. Atsakau remdamasis skaidrėmis arba bendromis medicinos žiniomis.")
        st.divider()

        # Rodome pokalbių istoriją
        chat_container = st.container(height=300)
        with chat_container:
            for msg in st.session_state["chat_messages"]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

        # Įvesties laukas
        if prompt := st.chat_input("Klausimas..."):
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})
            
            # Generuojame atsakymą su Gemini
            if client:
                chat_prompt = f"""
                Tu esi patyręs medicinos dėstytojas.
                Skaidrių medžiaga: {current_cycle_data['text'][:10000]}
                Klausimas: {prompt}
                
                Instrukcija: Jei atsakymas yra skaidrėse, atsakyk remdamasis jomis. Jei skaidrėse atsakymo nėra arba klausimas yra bendras medicininis / kitos srities klausimas, atsakyk naudodamasis savo bendrosiomis žiniomis, aiškiai ir profesionaliai lietuvių kalba.
                """
                try:
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=chat_prompt)
                    st.session_state["chat_messages"].append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.session_state["chat_messages"].append({"role": "assistant", "content": f"Klaida: {e}"})
            else:
                st.session_state["chat_messages"].append({"role": "assistant", "content": "⚠️ Nėra API rakto."})
            st.rerun()

# Fiksuojame konteinerį apatiniame dešiniajame kampo taške
float_box.float("bottom: 25px; right: 25px; position: fixed; z-index: 999999;")

# --- ATSKIRŲ PUSLAPIŲ LOGIKA SU PAŽANGIAIS ŽAIDIMAIS IR ŽVAIGŽDUTĖMIS ---

if "saved_items" not in st.session_state:
    st.session_state["saved_items"] = []

# Pagalbinė funkcija išsaugojimui su žvaigždute
def render_star_button(item_key, item_data):
    is_saved = any(item.get("key") == item_key for item in st.session_state["saved_items"])
    btn_label = "⭐ Pašalinti iš išsaugotų" if is_saved else "☆ Išsaugoti prie Mano klausimų"
    if st.button(btn_label, key=f"star_{item_key}"):
        if is_saved:
            st.session_state["saved_items"] = [i for i in st.session_state["saved_items"] if i.get("key") != item_key]
            st.success("Pašalinta iš išsaugotų!")
        else:
            st.session_state["saved_items"].append({"key": item_key, "data": item_data})
            st.success("Išsaugota prie Mano klausimų! ⭐")
        st.rerun()

# 1. KORTELĖS
if st.session_state["current_page"] == "Kortelės":
    st.subheader("🗂️ Aktyvaus prisiminimo kortelės")
    flashcards = current_cycle_data.get("flashcards", [])
    
    if not flashcards:
        st.warning("Šiam ciklui dar nėra kortelių. Sugeneruok jas Dashboard lange!")
    else:
        if "fc_index" not in st.session_state:
            st.session_state["fc_index"] = 0
            st.session_state["show_answer"] = False
            st.session_state["hard_cards"] = []

        idx = st.session_state["fc_index"]
        card = flashcards[idx]
        
        st.info(f"Kortelė {idx + 1} iš {len(flashcards)}")
        
        # Kortelės vaizdas
        with st.container():
            if not st.session_state["show_answer"]:
                st.markdown(f"### Klausimas / Vaistas / Dozė:\n**{card.get('klausimas')}**")
                if st.button("🔍 Rodyti atsakymą", key="show_ans_btn"):
                    st.session_state["show_answer"] = True
                    st.rerun()
            else:
                st.markdown(f"### Klausimas:\n{card.get('klausimas')}")
                st.markdown(f"### Atsakymas:\n🟢 **{card.get('atsakymas')}**")
                
                col_moku, col_nemoku = st.columns(2)
                with col_moku:
                    if st.button("🟢 Moku", key="btn_moku"):
                        st.session_state["show_answer"] = False
                        if idx < len(flashcards) - 1:
                            st.session_state["fc_index"] += 1
                        st.rerun()
                with col_nemoku:
                    if st.button("🔴 Nemoku (į pakartojimą)", key="btn_nemoku"):
                        if card not in st.session_state["hard_cards"]:
                            st.session_state["hard_cards"].append(card)
                        st.session_state["show_answer"] = False
                        if idx < len(flashcards) - 1:
                            st.session_state["fc_index"] += 1
                        st.rerun()
                        
                if st.button("🔍 Slėpti atsakymą", key="hide_ans_btn"):
                    st.session_state["show_answer"] = False
                    st.rerun()

        st.divider()
        render_star_button(f"fc_{idx}", card)

        col_prev, col_next = st.columns(2)
        with col_prev:
            if idx > 0 and st.button("⬅️ Ankstesnė", key="fc_prev"):
                st.session_state["fc_index"] -= 1
                st.session_state["show_answer"] = False
                st.rerun()
        with col_next:
            if idx < len(flashcards) - 1 and st.button("Kita ➔", key="fc_next"):
                st.session_state["fc_index"] += 1
                st.session_state["show_answer"] = False
                st.rerun()

# 2. VIKTORINA
elif st.session_state["current_page"] == "Viktorina":
    st.subheader("✏️ Žinių patikrinimo viktorina")
    quiz = current_cycle_data.get("quiz", [])
    
    if not quiz:
        st.warning("Šiam ciklui dar nėra viktorinos klausimų.")
    else:
        with st.expander("⚙️ Viktorinos nustatymai", expanded=True):
            difficulty = st.selectbox("Pasirink sudėtingumo lygį:", ["Lengvas (paviršinis)", "Vidutinis", "Sunkus (sujungiant kitas temas)"])
            max_q = st.slider("Klausimų skaičius:", 5, min(50, len(quiz)), min(10, len(quiz)))
            if st.button("Pradėti / Perkrauti testą", type="primary"):
                st.session_state["quiz_started"] = True
                st.rerun()

        if st.session_state.get("quiz_started", False):
            selected_quiz = quiz[:max_q]
            
            for i, q in enumerate(selected_quiz):
                st.markdown(f"**{i+1}. [{difficulty}] {q.get('klausimas')}**")
                ans = st.radio("Pasirink variantą:", q.get("variantai"), key=f"quiz_choice_{i}")
                
                if st.button(f"Tikrinti atsakymą #{i+1}", key=f"check_q_{i}"):
                    correct = q.get("teisingas")
                    if ans == correct:
                        st.success(f"Teisingai! 🎉 {q.get('paaiskinimas')}")
                    else:
                        st.error(f"Neteisingai. ❌ Teisingas atsakymas: **{correct}**. {q.get('paaiskinimas')}")
                
                render_star_button(f"quiz_{i}", q)
                st.divider()

# 3. DOCTORDLE
elif st.session_state["current_page"] == "Doctordle":
    st.subheader("🩺 Doctordle – Atspėk ligą iš užuominų")
    doctordle_data = current_cycle_data.get("doctordle", {})
    
    if not doctordle_data:
        st.warning("Šiam ciklui nėra sugeneruoto Doctordle atvejo.")
    else:
        if "doctordle_step" not in st.session_state:
            st.session_state["doctordle_step"] = 1
            st.session_state["doctordle_guessed"] = False

        uznuominos = doctordle_data.get("uzuoMINOS", [
            "1. Pacientas skundžiasi bendru silpnumu.",
            "2. Laboratoriniai tyrimai rodo nedidelius nukrypimus.",
            "3. Simptomai pasireiškia po fizinio krūvio.",
            "4. Būdingas specifinis klinikinis požymis.",
            "5. Tai labai dažna šios sistemos patologija."
        ])
        
        current_step = st.session_state["doctordle_step"]
        st.info(f"💡 Užuomina {current_step} iš {min(5, len(uznuominos))}")
        
        for i in range(min(current_step, len(uznuominos))):
            st.markdown(f"🔹 **Užuomina {i+1}:** {uznuominos[i]}")

        if current_step < len(uznuominos) and not st.session_state["doctordle_guessed"]:
            if st.button("➕ Gauti dar vieną užuominą (lengvesnę)"):
                st.session_state["doctordle_step"] += 1
                st.rerun()

        target_diagnosis = doctordle_data.get("liga", "Hipertenzija")
        guess = st.text_input("Įrašyk savo spėjimą (diagnozė):", placeholder="Pradėk rašyti ligos pavadinimą...")
        
        if st.button("Spėti diagnozę"):
            if guess.strip().lower() == target_diagnosis.strip().lower():
                st.success(f"🏆 Sveikinu! Teisinga diagnozė: **{target_diagnosis}**")
                st.session_state["doctordle_guessed"] = True
            else:
                st.error("Neteisinga diagnozė, bandyk dar kartą arba imk naują užuominą!")

        render_star_button("doctordle_case", doctordle_data)

# 4. POROS / DĖLIONĖS
elif st.session_state["current_page"] == "Poros":
    st.subheader("🔄 Porų / Dėlionių suderinimas")
    pairs = current_cycle_data.get("pairs", [])
    
    if not pairs:
        st.warning("Šiam ciklui nėra sugeneruotų porų.")
    else:
        st.write("Sujunk sąvokas su jų apibrėžimais arba vaistus su dozėmis:")
        for i, p in enumerate(pairs):
            st.markdown(f"**{i+1}. Sąvoka:** {p.get('kaire')}")
            user_choice = st.selectbox(f"Pasirink atitinkamą apibrėžimą #{i+1}", [p.get('desine'), "Kitas atsitiktinis variantas A", "Kitas atsitiktinis variantas B"], key=f"pair_{i}")
            if st.button(f"Tikrinti porą #{i+1}", key=f"check_pair_{i}"):
                if user_choice == p.get('desine'):
                    st.success("Teisinga pora! ✅")
                else:
                    st.error(f"Neteisingai. Teisingas variantas: **{p.get('desine')}**")
            render_star_button(f"pair_item_{i}", p)
            st.divider()

# 5. ŠPARGALKĖ
elif st.session_state["current_page"] == "Špargalkė":
    st.subheader("📜 Sutraukta špargalkė ir lentelės")
    cheatsheet = current_cycle_data.get("cheatsheet", "")
    if not cheatsheet:
        st.warning("Šiam ciklui dar nėra sugeneruotos špargalkelės.")
    else:
        st.markdown(cheatsheet)
        render_star_button("cheatsheet_main", {"text": cheatsheet})

# 6. MANO KLAUSIMAI (IŠSAUGOTI ELEMENTAI)
elif st.session_state["current_page"] == "Mano klausimai":
    st.subheader("⭐ Mano išsaugoti užrašai, kortelės ir atvejai")
    saved = st.session_state.get("saved_items", [])
    
    if not saved:
        st.info("Dar neišsaugojome nei vieno elemento. Spausk žvaigždutę žaidimuose ar kortelėse, kad juos čia rastum!")
    else:
        for idx, item in enumerate(saved):
            st.markdown(f"**Išsaugotas elementas #{idx + 1}**")
            st.json(item.get("data"))
            if st.button(f"Pašalinti iš sąrašo #{idx + 1}", key=f"remove_saved_{idx}"):
                st.session_state["saved_items"].pop(idx)
                st.rerun()
            st.divider()
            