import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import zh from './locales/zh.json'

const resources = {
  en: { translation: en },
  zh: { translation: zh },
}

// 从 localStorage 获取保存的语言，默认英文
const savedLanguage = localStorage.getItem('language') || 'en'

i18n.use(initReactI18next).init({
  resources,
  lng: savedLanguage,
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false, // React 已经处理了 XSS
  },
})

export default i18n
