import { useTranslation } from 'react-i18next'
import { Languages } from 'lucide-react'

export function LanguageSwitch() {
  const { i18n } = useTranslation()

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'zh' : 'en'
    i18n.changeLanguage(newLang)
    localStorage.setItem('language', newLang)
  }

  return (
    <button className="language-switch" onClick={toggleLanguage} title="Switch Language">
      <Languages size={18} />
      <span>{i18n.language === 'en' ? 'EN' : '中文'}</span>
    </button>
  )
}
