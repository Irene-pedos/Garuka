from typing import Any

from app.models.user import LanguageEnum

MESSAGES: dict[str, dict[LanguageEnum, str]] = {
    "S_ROLE_PICK": {
        LanguageEnum.en: "Garuka\n1. Staff menu\n2. Parent menu",
        LanguageEnum.rw: "Garuka\n1. Ibikorwa by'abarimu\n2. Ibikorwa by'ababyeyi",
        LanguageEnum.fr: "Garuka\n1. Menu personnel\n2. Menu parents",
    },
    "S_LANG": {
        LanguageEnum.en: "Language / Ururimi\n1. Kinyarwanda\n2. English\n3. Francais",
        LanguageEnum.rw: "Ururimi / Language\n1. Kinyarwanda\n2. English\n3. Francais",
        LanguageEnum.fr: "Langue / Ururimi\n1. Kinyarwanda\n2. English\n3. Francais",
    },
    "S_LANG_SAVED": {
        LanguageEnum.en: "Language saved. Dial again.",
        LanguageEnum.rw: "Ururimi rwahinduwe. Ongera uhamagare.",
        LanguageEnum.fr: "Langue enregistree. Recomposez.",
    },
    "S_UNREGISTERED": {
        LanguageEnum.en: "This number is not registered with Garuka. Please contact your school.",
        LanguageEnum.rw: "Iyi numero ntiyanditswe muri Garuka. Vugana n'ubuyobozi bw'ishuri.",
        LanguageEnum.fr: "Ce numero n'est pas enregistre sur Garuka. Contactez votre ecole.",
    },
    "S_ERROR": {
        LanguageEnum.en: "Service temporarily unavailable. Please try again.",
        LanguageEnum.rw: "Serivisi ntabwo ibonetse ako kanya. Ongera ugerageze.",
        LanguageEnum.fr: "Service temporairement indisponible. Veuillez reessayer.",
    },
    "S_INVALID": {
        LanguageEnum.en: "Invalid choice.\n",
        LanguageEnum.rw: "Ibyo uhisemo si byo.\n",
        LanguageEnum.fr: "Choix invalide.\n",
    },
    "T_PIN_SETUP1": {
        LanguageEnum.en: "Welcome to Garuka. Create a 4-digit PIN:",
        LanguageEnum.rw: "Murakaza neza muri Garuka. Shyiraho umubare w'ibanga w'imibare 4:",
        LanguageEnum.fr: "Bienvenue sur Garuka. Creez un code PIN a 4 chiffres:",
    },
    "T_PIN_SETUP2": {
        LanguageEnum.en: "Repeat your PIN:",
        LanguageEnum.rw: "Subiramo umubare w'ibanga:",
        LanguageEnum.fr: "Repetez votre code PIN:",
    },
    "T_PIN_SAVED": {
        LanguageEnum.en: "PIN saved. Dial again to start.",
        LanguageEnum.rw: "Umubare w'ibanga wabitswe. Ongera uhamagare utangire.",
        LanguageEnum.fr: "PIN enregistre. Recomposez pour commencer.",
    },
    "T_PIN_MISMATCH": {
        LanguageEnum.en: "PINs did not match. Dial again.",
        LanguageEnum.rw: "Imibare y'ibanga ntiyahuye. Ongera uhamagare.",
        LanguageEnum.fr: "Les codes PIN ne correspondent pas. Recomposez.",
    },
    "T_PIN_INVALID_RULES": {
        LanguageEnum.en: "PIN must be 4 digits and not simple (e.g. 0000, 1234). Dial again.",
        LanguageEnum.rw: "Umubare w'ibanga ugomba kuba imibare 4 idasanzwe (ntiwemerewe 0000 cyangwa 1234).",
        LanguageEnum.fr: "Le PIN doit avoir 4 chiffres et ne pas etre simple (ex. 0000, 1234).",
    },
    "T_PIN": {
        LanguageEnum.en: "Enter your PIN:",
        LanguageEnum.rw: "Injiza umubare w'ibanga:",
        LanguageEnum.fr: "Entrez votre code PIN:",
    },
    "T_PIN_WRONG": {
        LanguageEnum.en: "Wrong PIN. Dial again.",
        LanguageEnum.rw: "Umubare w'ibanga si wo. Ongera uhamagare.",
        LanguageEnum.fr: "Code PIN incorrect. Recomposez.",
    },
    "T_PIN_LOCKED": {
        LanguageEnum.en: "PIN locked. Contact your head teacher.",
        LanguageEnum.rw: "Konti yawe yafunzwe. Vugana n'umuyobozi w'ishuri.",
        LanguageEnum.fr: "PIN bloque. Contactez votre chef d'etablissement.",
    },
    "T_MENU": {
        LanguageEnum.en: "Garuka\n1. Mark absences\n2. Today's summary\n3. Flagged students\n4. Language",
        LanguageEnum.rw: "Garuka\n1. Kumenyekanisha abasibye\n2. Incamake y'uyu munsi\n3. Abanyeshuri bafite ikibazo\n4. Ururimi",
        LanguageEnum.fr: "Garuka\n1. Marquer absences\n2. Resume du jour\n3. Eleves signales\n4. Langue",
    },
    "T_DATE": {
        LanguageEnum.en: "Date:\n1. Today ({today})\n2. Yesterday ({yesterday})\n0. Back",
        LanguageEnum.rw: "Italiki:\n1. Uyu munsi ({today})\n2. Ejo hashize ({yesterday})\n0. Gusubira inyuma",
        LanguageEnum.fr: "Date:\n1. Aujourd'hui ({today})\n2. Hier ({yesterday})\n0. Retour",
    },
    "T_ALREADY": {
        LanguageEnum.en: "{class_name} {date_str} already saved ({n} absent).\n1. Replace it\n0. Back",
        LanguageEnum.rw: "{class_name} ku wa {date_str} byarabitswe ({n} basibye).\n1. Hindura\n0. Subira inyuma",
        LanguageEnum.fr: "{class_name} {date_str} deja enregistre ({n} absents).\n1. Remplacer\n0. Retour",
    },
    "T_ROLL": {
        LanguageEnum.en: "{prefix}Absent: {n} so far.\nEnter roll no. ({min_roll}-{max_roll}).\n0 = finish\n00 = cancel",
        LanguageEnum.rw: "{prefix}Abasibye kugeza ubu: {n}.\nInjiza numero y'umunyeshuri ({min_roll}-{max_roll}).\n0 = kurangiza\n00 = guhagarika",
        LanguageEnum.fr: "{prefix}Absents actuels: {n}.\nEntrez numero ({min_roll}-{max_roll}).\n0 = terminer\n00 = annuler",
    },
    "T_CONFIRM": {
        LanguageEnum.en: "{n} absent: {rolls}.\n1. Save\n2. Cancel",
        LanguageEnum.rw: "{n} basibye: {rolls}.\n1. Bika\n2. Hagarika",
        LanguageEnum.fr: "{n} absents: {rolls}.\n1. Enregistrer\n2. Annuler",
    },
    "T_CONFIRM_ALL_PRESENT": {
        LanguageEnum.en: "No absences: all present?\n1. Yes, save\n2. Cancel",
        LanguageEnum.rw: "Ntawasibye: bose bahari?\n1. Yego, bika\n2. Hagarika",
        LanguageEnum.fr: "Aucune absence: tous presents?\n1. Oui, enregistrer\n2. Annuler",
    },
    "T_COMMIT_SUCCESS": {
        LanguageEnum.en: "Saved. {n} absent in {class_name} on {date_str}. Parents will get an SMS.",
        LanguageEnum.rw: "Byabitswe. {n} basibye muri {class_name} ku wa {date_str}. Ababyeyi barohererezwa ubutumwa.",
        LanguageEnum.fr: "Enregistre. {n} absents en {class_name} le {date_str}. Les parents recevront un SMS.",
    },
    "T_SUMMARY": {
        LanguageEnum.en: "Today {date_str}:\n{lines}",
        LanguageEnum.rw: "Uyu munsi {date_str}:\n{lines}",
        LanguageEnum.fr: "Aujourd'hui {date_str}:\n{lines}",
    },
    "T_FLAGGED": {
        LanguageEnum.en: "Flagged:\n{lines}",
        LanguageEnum.rw: "Abafite ikibazo:\n{lines}",
        LanguageEnum.fr: "Signales:\n{lines}",
    },
}


def get_msg(key: str, lang: LanguageEnum = LanguageEnum.rw, **kwargs: Any) -> str:
    screen_dict = MESSAGES.get(key, {})
    template = screen_dict.get(lang) or screen_dict.get(LanguageEnum.en) or key
    if kwargs:
        return template.format(**kwargs)
    return template
