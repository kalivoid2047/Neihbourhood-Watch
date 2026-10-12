import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, AlertCircle, Users, MapPin, Bell, Siren, BadgeCheck, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Button, Tilt } from '../components/ui';
import { PageContent } from '../components/layout';

/** Layered CSS-3D scene that follows the pointer. */
function Hero3D() {
  const stage = useRef(null);

  const move = (e) => {
    const el = stage.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `rotateX(${(58 - y * 14).toFixed(2)}deg) rotateZ(${(-32 + x * 16).toFixed(2)}deg)`;
  };
  const leave = () => {
    if (stage.current) stage.current.style.transform = '';
  };

  const pins = [
    { left: '22%', top: '30%', color: '#ef4444', delay: '0s' },
    { left: '64%', top: '22%', color: '#f59e0b', delay: '-1.4s' },
    { left: '48%', top: '58%', color: '#22d3ee', delay: '-2.6s' },
    { left: '76%', top: '66%', color: '#22c55e', delay: '-3.8s' },
  ];

  return (
    <div className="relative h-[460px] scene hidden md:block" onPointerMove={move} onPointerLeave={leave} aria-hidden="true">
      {/* Isometric map slab */}
      <div
        ref={stage}
        className="absolute left-1/2 top-1/2 w-[400px] h-[400px] -ml-[200px] -mt-[190px] preserve-3d"
        style={{ transform: 'rotateX(58deg) rotateZ(-32deg)', transition: 'transform .25s ease-out' }}
      >
        {/* slab thickness */}
        <div className="absolute inset-0 rounded-3xl" style={{ transform: 'translateZ(-26px)', background: '#0b1230', boxShadow: '0 60px 80px -10px rgba(0,0,0,.7), 0 0 60px rgba(34,211,238,.25)' }} />
        <div className="absolute inset-0 rounded-3xl glass overflow-hidden" style={{ transform: 'translateZ(0)' }}>
          <div className="absolute inset-0 opacity-60" style={{ backgroundImage: 'linear-gradient(rgba(103,232,249,.25) 1px, transparent 1px), linear-gradient(90deg, rgba(103,232,249,.25) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
          <div className="absolute w-44 h-44 rounded-full border border-cyan-300/50" style={{ left: '30%', top: '36%', boxShadow: '0 0 40px rgba(34,211,238,.35) inset' }} />
          <div className="absolute w-24 h-24 rounded-full border border-violet-300/40" style={{ left: '10%', top: '10%' }} />
          <div className="absolute h-[3px] w-[70%] bg-cyan-300/40 rotate-[24deg]" style={{ left: '12%', top: '48%' }} />
          <div className="absolute h-[3px] w-[55%] bg-violet-300/40 -rotate-[38deg]" style={{ left: '34%', top: '62%' }} />
        </div>

        {/* floating pins that stand up off the slab */}
        {pins.map((p, i) => (
          <div key={i} className="absolute preserve-3d" style={{ left: p.left, top: p.top, transform: 'translateZ(6px)' }}>
            {/* counter-rotate so the pin faces the camera; the float animation lives on the child */}
            <div className="preserve-3d" style={{ transformOrigin: 'bottom', transform: 'rotateZ(32deg) rotateX(-58deg)' }}>
              <div className="animate-float" style={{ '--z': '40px', animationDelay: p.delay }}>
                <div className="relative w-9 h-9 rounded-full flex items-center justify-center" style={{ background: p.color, boxShadow: `0 0 22px ${p.color}` }}>
                  <span className="absolute inset-0 rounded-full animate-ping2" style={{ background: p.color, opacity: 0.5 }} />
                  <MapPin className="relative w-5 h-5 text-white" />
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* orbit ring */}
        <div className="absolute rounded-full border-2 border-dashed border-cyan-300/40" style={{ inset: '-40px', transform: 'translateZ(50px)', animation: 'spin 40s linear infinite' }} />
      </div>

      {/* Foreground chips (parallax layer, un-rotated) */}
      <div className="absolute left-2 top-10 animate-float" style={{ '--z': '60px' }}>
        <Tilt max={14} lift={30} className="glass glass-strong !rounded-2xl px-4 py-3 flex items-center gap-3">
        <span className="w-9 h-9 rounded-xl bg-emerald-400/20 border border-emerald-300/30 flex items-center justify-center"><BadgeCheck className="w-5 h-5 text-emerald-300" /></span>
        <div><p className="text-sm font-semibold text-white">Incident verified</p><p className="text-xs text-slate-400">by your coordinator</p></div>
      </Tilt>
      </div>
      <div className="absolute right-0 top-32 animate-float" style={{ '--z': '80px', animationDelay: '-2s' }}>
        <Tilt max={14} lift={40} className="glass glass-strong !rounded-2xl px-4 py-3 flex items-center gap-3">
        <span className="w-9 h-9 rounded-xl bg-red-400/20 border border-red-300/30 flex items-center justify-center"><Siren className="w-5 h-5 text-red-300" /></span>
        <div><p className="text-sm font-semibold text-white">SOS active</p><p className="text-xs text-slate-400">2 responders nearby</p></div>
      </Tilt>
      </div>
      <div className="absolute left-10 bottom-6 animate-float" style={{ '--z': '50px', animationDelay: '-4s' }}>
        <Tilt max={14} lift={30} className="glass glass-strong !rounded-2xl px-4 py-3 flex items-center gap-3">
        <span className="w-9 h-9 rounded-xl bg-cyan-400/20 border border-cyan-300/30 flex items-center justify-center"><Bell className="w-5 h-5 text-cyan-300" /></span>
        <div><p className="text-sm font-semibold text-white">New alert</p><p className="text-xs text-slate-400">Within 1.2 km</p></div>
      </Tilt>
      </div>
    </div>
  );
}

const FEATURES = [
  { icon: AlertCircle, title: 'Report Incidents', description: 'Report security incidents in seconds, pinned to the exact spot on the map.' },
  { icon: Bell, title: 'Real-Time Alerts', description: 'Instant notifications and live status updates the moment an incident changes.' },
  { icon: MapPin, title: 'Live Safety Map', description: 'Explore incidents, heat zones and neighbourhood boundaries on an interactive map.' },
  { icon: Users, title: 'Community Response', description: 'Coordinate with verified residents, block captains and police liaisons.' },
  { icon: Shield, title: 'Verified Community', description: 'A verification workflow builds trust between neighbours and responders.' },
  { icon: Siren, title: 'Emergency SOS', description: 'One press shares your live location with emergency contacts and coordinators.' },
];

const STEPS = [
  { title: 'Register', desc: 'Create your account and confirm your phone.' },
  { title: 'Verify', desc: 'Get verified by a coordinator.' },
  { title: 'Report', desc: 'Log incidents with a map pin and details.' },
  { title: 'Respond', desc: 'Follow live updates and coordinate together.' },
];

export default function HomePage({ user }) {
  const navigate = useNavigate();

  return (
    <div>
      {/* Hero */}
      <section className="pt-10 pb-16">
        <PageContent>
          <div className="grid md:grid-cols-2 gap-10 items-center">
            <div className="animate-rise">
              <span className="inline-flex items-center gap-2 glass !rounded-full px-3.5 py-1.5 text-xs font-semibold text-cyan-200 mb-6">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" /> Community safety for Zimbabwe
              </span>
              <h1 className="text-5xl lg:text-6xl font-extrabold leading-[1.05] mb-6">
                Safer streets,<br /><span className="text-gradient">built together.</span>
              </h1>
              <p className="text-lg text-slate-300 mb-8 max-w-xl">
                Neighbourhood Watch Zimbabwe connects residents, block captains, coordinators and responders through live incident reporting, an interactive safety map and one-touch SOS.
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                {user ? (
                  <>
                    <Button size="lg" onClick={() => navigate('/incidents')}>Open incidents <ArrowRight className="w-5 h-5" /></Button>
                    <Button size="lg" variant="secondary" onClick={() => navigate('/map')}>View live map</Button>
                  </>
                ) : (
                  <>
                    <Button size="lg" onClick={() => navigate('/register')}>Get started <ArrowRight className="w-5 h-5" /></Button>
                    <Button size="lg" variant="secondary" onClick={() => navigate('/login')}>Sign in</Button>
                  </>
                )}
              </div>
              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400">
                {['Live updates', 'Role-based access', 'Works on mobile'].map((t) => (
                  <li key={t} className="flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4 text-emerald-400" />{t}</li>
                ))}
              </ul>
            </div>
            <Hero3D />
          </div>
        </PageContent>
      </section>

      {/* Features */}
      <section className="py-14">
        <PageContent>
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-3">Everything a neighbourhood needs</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">From the first report to the final resolution, in one place.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 stagger">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <Tilt key={title} max={7} lift={10} className="glass glass-interactive p-7">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400/30 to-violet-500/30 border border-white/20 flex items-center justify-center mb-5" style={{ transform: 'translateZ(30px)', boxShadow: '0 12px 24px -8px rgba(34,211,238,.45)' }}>
                  <Icon className="w-6 h-6 text-cyan-200" />
                </div>
                <h3 className="text-lg font-semibold mb-2" style={{ transform: 'translateZ(20px)' }}>{title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
              </Tilt>
            ))}
          </div>
        </PageContent>
      </section>

      {/* How it works */}
      <section className="py-14">
        <PageContent>
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-3">How it works</h2>
            <p className="text-slate-400">Four simple steps to a safer neighbourhood.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 stagger">
            {STEPS.map((s, i) => (
              <Tilt key={s.title} max={9} lift={12} className="glass p-6 text-center">
                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gradient-to-b from-cyan-300 to-cyan-600 text-ink-950 flex items-center justify-center text-xl font-extrabold font-display" style={{ transform: 'translateZ(34px)', boxShadow: '0 5px 0 #0e7490, 0 16px 24px -6px rgba(34,211,238,.5)' }}>
                  {i + 1}
                </div>
                <h3 className="font-semibold mb-1">{s.title}</h3>
                <p className="text-sm text-slate-400">{s.desc}</p>
              </Tilt>
            ))}
          </div>
        </PageContent>
      </section>

      {/* CTA */}
      {!user && (
        <section className="py-14">
          <PageContent>
            <Tilt max={4} glare className="glass glass-strong !rounded-3xl text-center px-6 py-14 relative overflow-hidden">
              <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[520px] h-[260px] rounded-full bg-cyan-400/25 blur-3xl" aria-hidden="true" />
              <h2 className="relative text-3xl sm:text-4xl font-bold mb-3">Ready to make a difference?</h2>
              <p className="relative text-slate-300 mb-8 max-w-xl mx-auto">Join residents building safer neighbourhoods across Zimbabwe.</p>
              <Button size="lg" className="relative" onClick={() => navigate('/register')}>Create your account <ArrowRight className="w-5 h-5" /></Button>
            </Tilt>
          </PageContent>
        </section>
      )}
    </div>
  );
}
