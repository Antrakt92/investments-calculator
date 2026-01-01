import { useState, ReactNode } from 'react'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
}

export default function Tooltip({ content, children, position = 'top' }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)

  const positionStyles: Record<string, React.CSSProperties> = {
    top: {
      bottom: '100%',
      left: '50%',
      transform: 'translateX(-50%)',
      marginBottom: '8px',
    },
    bottom: {
      top: '100%',
      left: '50%',
      transform: 'translateX(-50%)',
      marginTop: '8px',
    },
    left: {
      right: '100%',
      top: '50%',
      transform: 'translateY(-50%)',
      marginRight: '8px',
    },
    right: {
      left: '100%',
      top: '50%',
      transform: 'translateY(-50%)',
      marginLeft: '8px',
    },
  }

  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          style={{
            position: 'absolute',
            ...positionStyles[position],
            backgroundColor: 'rgba(32, 33, 36, 0.95)',
            color: 'white',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '13px',
            lineHeight: '1.4',
            whiteSpace: 'normal',
            width: 'max-content',
            maxWidth: '280px',
            zIndex: 1000,
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            pointerEvents: 'none',
          }}
        >
          {content}
        </div>
      )}
    </span>
  )
}

// Helper component for info icon with tooltip
interface HelpIconProps {
  text: ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
}

export function HelpIcon({ text, position = 'top' }: HelpIconProps) {
  return (
    <Tooltip content={text} position={position}>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '16px',
          height: '16px',
          borderRadius: '50%',
          backgroundColor: 'var(--bg-secondary)',
          color: 'var(--text-secondary)',
          fontSize: '11px',
          fontWeight: 600,
          cursor: 'help',
          marginLeft: '6px',
        }}
      >
        ?
      </span>
    </Tooltip>
  )
}

// Tax term definitions for consistent help text
export const TAX_TERMS = {
  CGT: 'Capital Gains Tax (33%) applies to profits from selling stocks and non-EU ETFs. You get a €1,270 annual exemption per person.',

  EXIT_TAX: 'Exit Tax (41%) applies to Irish/EU domiciled ETFs and funds. No annual exemption. Losses can offset gains within Exit Tax only.',

  DIRT: 'Deposit Interest Retention Tax (33%) applies to interest earned on savings and deposits. Trade Republic does NOT withhold DIRT - you must declare it.',

  DEEMED_DISPOSAL: 'The 8-year rule: EU funds are taxed as if sold every 8 years, even if you don\'t sell. This is to prevent indefinite tax deferral.',

  BED_BREAKFAST: 'The 4-week rule: If you sell and rebuy the same asset within 4 weeks, the cost basis of the repurchase is used for the sale, potentially reducing loss relief.',

  FIFO: 'First In, First Out: When selling, the oldest shares are matched first for calculating gains/losses.',

  EXEMPTION: '€1,270 per person per year. In family mode, each person gets their own exemption. Only applies to CGT, not Exit Tax.',

  FORM_11: 'Irish Revenue\'s annual tax return for self-assessed income, capital gains, and other taxes. Due by October 31st for paper, November 14th for ROS.',

  PPS_NUMBER: 'Personal Public Service Number - your unique Irish tax identifier. Required for Revenue filings.',

  WITHHOLDING_TAX: 'Tax deducted at source by foreign countries on dividends. You can claim this as a credit against Irish tax.',
}
