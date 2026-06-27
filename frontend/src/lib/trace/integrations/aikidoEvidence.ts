/**
 * Aikido adapter — security evidence for the build.
 *
 * Checks whether the Aikido security report screenshot exists in docs/.
 * Returns evidence metadata for the sponsor panel.
 */

import fs from 'fs'
import path from 'path'

export interface AikidoEvidence {
  screenshot_present: boolean
  screenshot_path: string
  report_url: string | null
  status: 'screenshot_present' | 'screenshot_required'
  message: string
}

export function getAikidoEvidence(): AikidoEvidence {
  const screenshotPath = path.join(process.cwd(), '..', 'docs', 'aikido-security-report.png')
  const reportUrl = process.env.AIKIDO_REPORT_URL ?? null

  const exists = (() => {
    try {
      return fs.existsSync(screenshotPath)
    } catch {
      return false
    }
  })()

  if (exists) {
    return {
      screenshot_present: true,
      screenshot_path: screenshotPath,
      report_url: reportUrl,
      status: 'screenshot_present',
      message: 'Aikido security report screenshot found in docs/. Security scan evidence available.',
    }
  }

  return {
    screenshot_present: false,
    screenshot_path: screenshotPath,
    report_url: reportUrl,
    status: 'screenshot_required',
    message: 'Aikido security report screenshot not found. Please add docs/aikido-security-report.png.',
  }
}

export function aikidoStatus(): 'screenshot_present' | 'screenshot_required' {
  return getAikidoEvidence().status
}
