export async function getHealth() {
  const response = await fetch('/api/v1/monitoring/health')

  if (!response.ok) {
    throw new Error('Failed to fetch health status')
  }

  return response.json()
}
