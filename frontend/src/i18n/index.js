import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import en from './locales/en.json';
import fr from './locales/fr.json';
export const SUPPORTED_LANGUAGES = ['en', 'fr'];
void i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
    resources: {
        en: { translation: en },
        fr: { translation: fr },
    },
    fallbackLng: 'en',
    supportedLngs: SUPPORTED_LANGUAGES,
    nonExplicitSupportedLngs: true,
    interpolation: {
        escapeValue: false,
    },
    detection: {
        order: ['localStorage', 'navigator', 'htmlTag'],
        caches: ['localStorage'],
        lookupLocalStorage: 'adminator.lang',
    },
    returnNull: false,
});
function applyHtmlLang(lng) {
    const short = lng.split('-')[0];
    document.documentElement.lang = short;
}
applyHtmlLang(i18n.language || 'en');
i18n.on('languageChanged', applyHtmlLang);
export default i18n;
