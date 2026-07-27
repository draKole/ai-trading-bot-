export default function Accounts() {
  const accounts = [
    {
      broker: "Paper Trading",
      account: "SIM-50000",
      status: "Connected",
      balance: "$50,000",
      buyingPower: "$50,000",
      pnl: "$0.00",
      positions: 0,
    },
  ]

  return (
    <div className="p-6">
      <h2 className="text-3xl font-bold mb-6">Accounts</h2>

      <div className="grid gap-6">
        {accounts.map((account) => (
          <div
            key={account.account}
            className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold">
                  {account.broker}
                </h3>

                <p className="text-slate-400">
                  {account.account}
                </p>
              </div>

              <span className="rounded bg-green-900 px-3 py-1 text-green-400">
                {account.status}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-8">
              <div>
                <p className="text-sm text-slate-500">Balance</p>
                <p className="text-lg font-bold">{account.balance}</p>
              </div>

              <div>
                <p className="text-sm text-slate-500">
                  Buying Power
                </p>

                <p className="text-lg font-bold">
                  {account.buyingPower}
                </p>
              </div>

              <div>
                <p className="text-sm text-slate-500">
                  Today's P/L
                </p>

                <p className="text-lg font-bold text-green-400">
                  {account.pnl}
                </p>
              </div>

              <div>
                <p className="text-sm text-slate-500">
                  Open Positions
                </p>

                <p className="text-lg font-bold">
                  {account.positions}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
