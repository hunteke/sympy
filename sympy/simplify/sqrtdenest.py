from sympy.functions import sqrt, sign, root
from sympy.core import S, Wild, sympify, Mul, Add, Expr
from sympy.core.function import expand_multinomial, expand_mul
from sympy.core.symbol import Dummy
from sympy.polys import Poly, PolynomialError

def _mexpand(expr):
    return expand_mul(expand_multinomial(expr))

def is_sqrt(expr):
    # XXX expr.exp.q == 2?
    return expr.is_Pow and expr.exp.is_Rational and abs(expr.exp) is S.Half

def _sqrt_symbolic_denest(a, b, r):
    """
    Given an expression, sqrt(a + b*sqrt(b)), return the denested
    expression or None.

    Algorithm:
    If r = ra + rb*sqrt(rr), try replacing sqrt(rr) in a with (y**2 - ra)/rb,
    and if the result is a quadratic, ca*y**2 + cb*y + cc, and has a
    discriminant of 0, then sqrt(a + b*sqrt(r)) can be rewritten as
    sqrt(ca*(sqrt(r) + cb/(2*ca))**2). XXX a simple example would be nice

    Examples
    ========
    >>> from sympy.simplify.sqrtdenest import _sqrt_symbolic_denest, sqrtdenest
    >>> from sympy import sqrt, Symbol
    >>> from sympy.abc import x

    >>> _sqrt_symbolic_denest(16 - 2*sqrt(29), 2, -10*sqrt(29) + 55)
    sqrt(-2*sqrt(29) + 11) + sqrt(5)

    If the expression is numeric, it will be simplified:

    >>> w = sqrt(sqrt(sqrt(3) + 1) + 1) + 1 + sqrt(2)
    >>> sqrtdenest(sqrt((w**2).expand()))
    1 + sqrt(2) + sqrt(1 + sqrt(1 + sqrt(3)))

    Otherwise, it will only be simplified if assumptions allow:

    >>> w = w.subs(sqrt(3), sqrt(x + 3))
    >>> sqrtdenest(sqrt((w**2).expand()))
    sqrt((sqrt(sqrt(sqrt(x + 3) + 1) + 1) + 1 + sqrt(2))**2)

    Notice that the argument of the sqrt is a square. If x is made positive
    then the sqrt of the square is resolved:

    >>> _.subs(x, Symbol('x', positive=True))
    sqrt(sqrt(sqrt(x + 3) + 1) + 1) + 1 + sqrt(2)
    """

    a, b, r = sympify([a, b, r])
    rval = sqrt_match(r)
    if not rval:
        return None
    ra, rb, rr = rval
    if rb:
        y = Dummy('y', positive=True)
        try:
            newa = Poly(a.subs(sqrt(rr), (y**2 - ra)/rb), y)
        except PolynomialError:
            return None
        if newa.degree() == 2:
            ca, cb, cc = newa.all_coeffs()
            cb += b
            if _mexpand(cb**2 - 4*ca*cc).equals(0):
                z = sqrt(ca*(sqrt(r) + cb/(2*ca))**2)
                if z.is_number:
                    z = _mexpand(Mul._from_args(z.as_content_primitive()))
                return z

def sqrt_numeric_denest(a, b, r, d2):
    """
    denest expr = a + b*sqrt(r), with d2 = a**2 - b**2*r > 0

    If not denested return None
    """
    from sympy.simplify.simplify import radsimp
    depthr = sqrt_depth(r)
    d = sqrt(d2)
    vad = a + d
    # sqrt_depth(res) <= sqrt_depth(vad) + 1
    # sqrt_depth(expr) = depthr + 2
    # there is denesting if sqrt_depth(vad)+1 < depthr + 2
    # if vad**2 is Number there is a fourth root
    if sqrt_depth(vad) < depthr + 1 or (vad**2).is_Rational:
        vad1 = radsimp(1/vad)
        return (sqrt(vad/2) + sign(b)*sqrt((b**2*r*vad1/2).expand())).expand()


def _sqrt_four_terms_denest(expr):
    """Helper that denests the square root of three or four surds.

    Examples
    ========
    >>> from sympy import sqrt
    >>> from sympy.simplify.sqrtdenest import _sqrt_four_terms_denest
    >>> _sqrt_four_terms_denest(sqrt(-72*sqrt(2) + 158*sqrt(5) + 498))
    -sqrt(10) + sqrt(2) + 9 + 9*sqrt(5)
    >>> _sqrt_four_terms_denest(sqrt(12+2*sqrt(6)+2*sqrt(14)+2*sqrt(21)))
    sqrt(2) + sqrt(3) + sqrt(7)

    References
    ==========
    - D. J. Jeffrey and A. D. Rich, 'Symplifying Square Roots of Square Roots
      by Denesting'

    """
    from sympy.simplify.simplify import radsimp
    assert is_sqrt(expr)
    if expr.base < 0:
        return sqrt(-1)*_sqrt_four_terms_denest(sqrt(-expr.base))
    a = Add(*expr.base.args[:2])
    b = Add(*expr.base.args[2:])
    if a < 0:
        a, b = b, a
    d2 = _mexpand(a**2 - b**2)
    if d2 < 0:
        a, b = b, a
        d2 = -d2
    d = _sqrtdenest(sqrt(d2))
    if sqrt_depth(d) > 1:
        return expr
    vad = a + d
    c = _sqrtdenest(sqrt(vad))
    if sqrt_depth(c) > 1:
        return expr
    return radsimp((c/sqrt(2) + b/(sqrt(2)*c))).expand()


def sqrtdenest(expr, max_iter=3):
    """
    Denests sqrts in an expression that contain other square roots
    if possible, otherwise return the expr unchanged. This is based on the
    algorithm of [1].

    Examples
    ========

    >>> from sympy.simplify.sqrtdenest import sqrtdenest
    >>> from sympy import sqrt
    >>> sqrtdenest(sqrt(5 + 2 * sqrt(6)))
    sqrt(2) + sqrt(3)

    See Also
    ========
    sympy.solvers.solvers.unrad

    References
    ==========
    [1] http://www.almaden.ibm.com/cs/people/fagin/symb85.pdf

    """
    expr = expand_mul(sympify(expr))
    for i in range(max_iter):
        z = sqrtdenest0(expr)
        if expr == z:
            return expr
        expr = z
    return expr


def sqrtdenest0(expr):
    """XXX docstring needed"""

    if is_sqrt(expr):
        n, d = expr.as_numer_denom()
        if d is S.One:
            if n.base.is_Add:
                nn = len(n.base.args)
                if 3 <= nn <= 4 and all([(x**2).is_Rational for x in n.base.args]):
                    return _sqrt_four_terms_denest(n)
                expr = sqrt(_mexpand(Add(*[sqrtdenest0(x) for x in n.base.args])))
            return _sqrtdenest(expr)
        else:
            n, d = [sqrtdenest0(i) for i in (n, d)]
            return n/d
    if isinstance(expr, Expr):
        args = expr.args
        if args:
            return expr.func(*[sqrtdenest0(a) for a in args])
    return expr

def _sqrtdenest(expr):
    """XXX docstring needed"""

    from sympy.simplify.simplify import radsimp
    if not is_sqrt(expr):
        val = None
    else:
        a = expr.base
        if a.is_Number:
            return expr
        if not a.args:
            val = (a, S.Zero, S.Zero)
        val = sqrt_match(a)

    if val:
        a, b, r = val
        # try a quick numeric denesting
        d2 = _mexpand(a**2 - b**2*r)
        if d2.is_Rational:
            if d2.is_positive:
                z = sqrt_numeric_denest(a, b, r, d2)
                if z != None:
                    return z
            else:
                # fourth root case
                # sqrtdenest(sqrt(3 + 2*sqrt(3))) =
                # sqrt(2)*3**(1/4)/2 + sqrt(2)*3**(3/4)/2
                dr2 = _mexpand(-d2*r)
                dr = sqrt(dr2)
                if dr.is_Rational:
                    z = sqrt_numeric_denest(_mexpand(b*r), a, r, dr2)
                    if z != None:
                        return z/root(r, 4)

        else:
            z = _sqrt_symbolic_denest(a, b, r)
            if z != None:
                return z

    else:
        return expr
    if not expr.is_number:
        return expr
    if not is_algebraic(expr):
        return expr
    av0 = [a, b, r, d2]
    z = _denester([radsimp(expr**2)], av0, 0, sqrt_depth(expr)-1)[0]
    if av0[1] == None:
        return expr
    if z != None:
        return z
    return expr

def sqrt_depth(p):
    """
    XXX docstring needed

    >>> from sympy.functions.elementary.miscellaneous import sqrt
    >>> from sympy.simplify.sqrtdenest import sqrt_depth
    >>> sqrt_depth(1 + sqrt(2)*(1 + sqrt(3)))
    1
    >>> sqrt_depth(1 + sqrt(2)*sqrt(1 + sqrt(3)))
    2
    """
    if p.is_Atom:
        return 0
    elif p.is_Add or p.is_Mul:
        return max([sqrt_depth(x) for x in p.args])
    elif is_sqrt(p):
        return sqrt_depth(p.base) + 1
    else:
        return 0

def is_algebraic(p):
    """
    XXX docstring needed
    >>> from sympy.functions.elementary.miscellaneous import sqrt
    >>> from sympy.simplify.sqrtdenest import is_algebraic
    >>> from sympy import cos
    >>> is_algebraic(sqrt(2)*(3/(sqrt(7) + sqrt(5)*sqrt(2))))
    True
    >>> is_algebraic(sqrt(2)*(3/(sqrt(7) + sqrt(5)*cos(2))))
    False
    """
    if p.is_Rational:
        return True
    elif p.is_Atom:
        return False
    elif is_sqrt(p) or p.is_Pow and p.exp == -1: # XXX p.exp.is_Integer?
        return is_algebraic(p.base)
    elif p.is_Add or p.is_Mul:
        return all([is_algebraic(x) for x in p.args])
    else:
        return False

def sqrt_match(p):
    """Return [a, b, r] for match p = a + b*sqrt(r) where
    sqrt(r) has maximal nested sqrt among addends of p.

    # FIXME should one count also fourth roots, or maybe any root?

    Examples
    ========
    >>> from sympy.functions.elementary.miscellaneous import sqrt
    >>> from sympy.simplify.sqrtdenest import sqrt_match
    >>> sqrt_match(1 + sqrt(2) + sqrt(2)*sqrt(3) +  2*sqrt(1+sqrt(5)))
    [1 + sqrt(2) + sqrt(6), 2, 1 + sqrt(5)]
    """
    p = _mexpand(p)
    if p.is_Number:
        res = (p, S.Zero, S.Zero)
    elif p.is_Add:
        pargs = list(p.args)
        v = [(sqrt_depth(x), i) for i, x in enumerate(pargs)]
        nmax = max(v)
        if nmax[0] == 0:
            res = []
        else:
            depth = nmax[0]
            n = nmax[1]
            p1 = pargs[n]
            del pargs[n]
            a = Add(*pargs)
            bv = []
            rv = []
            if p1.is_Mul:
                for x in p1.args:
                    if sqrt_depth(x) < depth:
                        bv.append(x)
                    else:
                        rv.append(x)

                b = Mul(*bv)
                r = Mul(*rv)
            else:
                b = S.One
                r = p1
            res = (a, b, r**2)
    else:
        b, r = p.as_coeff_Mul()
        if is_sqrt(r):
            res = (S.Zero, b, r**2)
        else:
            res = []
    return list(res)

def _denester (nested, av0, h, max_depth_level):
    """
    Denests a list of expressions that contain nested square roots.
    This method should not be called directly - use 'sqrtdenest' instead.
    This algorithm is based on <http://www.almaden.ibm.com/cs/people/fagin/symb85.pdf>.

    It is assumed that all of the elements of 'nested' share the same
    bottom-level radicand. (This is stated in the paper, on page 177, in
    the paragraph immediately preceding the algorithm.)

    When evaluating all of the arguments in parallel, the bottom-level
    radicand only needs to be denested once. This means that calling
    _denester with x arguments results in a recursive invocation with x+1
    arguments; hence _denester has polynomial complexity.

    However, if the arguments were evaluated separately, each call would
    result in two recursive invocations, and the algorithm would have
    exponential complexity.

    This is discussed in the paper in the middle paragraph of page 179.
    """
    from sympy.simplify.simplify import radsimp
    if h > max_depth_level:
        return None, None
    if av0[1] == None:
        return None, None
    #If none of the arguments are nested
    if av0[0] == None and all(n.is_Number for n in nested): #If none of the arguments are nested
        for f in subsets(len(nested)): #Test subset 'f' of nested
            p = _mexpand(Mul(*[nested[i] for i in range(len(f)) if f[i]]))
            if 1 in f and f.count(1) > 1 and f[-1]:
                p = -p
            sqp = sqrt(p)
            if sqp.is_Number:
                return sqp, f #If we got a perfect square, return its square root.
        return sqrt(nested[-1]), [0]*len(nested) #Otherwise, return the radicand from the previous invocation.
    else:
        R = None
        if av0[0] != None:
            values = [av0[:2]]
            R = av0[2]
            nested2 = [av0[3], R]
            av0[0] = None
        else:
            values = filter(None, [sqrt_match(expr) for expr in nested])
            for v in values:
                if v[2]: #Since if b=0, r is not defined
                    if R is not None:
                        if R != v[2]:
                            av0[1] = None
                            return None, None
                        #assert R == v[2] #All the 'r's should be the same.
                    else:
                        R = v[2]
            if R is None:
                return sqrt(nested[-1]), [0]*len(nested) # return the radicand from the previous invocation
            nested2 = [_mexpand(v[0]**2) - _mexpand(R*v[1]**2) for v in values] + [R]
        d, f = _denester(nested2, av0, h+1, max_depth_level)
        if not f:
            return None, None
        if not any(f[i] for i in range(len(nested))):
            v = values[-1]
            return sqrt(v[0] + v[1]*d), f
        else:
            p = Mul(*[nested[i] for i in range(len(nested)) if f[i]])
            v = sqrt_match(p)
            if 1 in f and f.index(1) < len(nested) - 1 and f[len(nested) - 1]:
                v[0] = -v[0]
                v[1] = -v[1]
            if not f[len(nested)]: #Solution denests with square roots
                vad = _mexpand(v[0] + d)
                if vad <= 0:
                    return sqrt(nested[-1]), [0]*len(nested) #Otherwise, return the radicand from the previous invocation.
                if not(sqrt_depth(vad) < sqrt_depth(R) + 1 or (vad**2).is_Number):
                    av0[1] = None
                    return None, None

                vad1 = radsimp(1/vad)
                return _mexpand(sqrt(vad/2) + sign(v[1])*sqrt(_mexpand(v[1]**2*R*vad1/2))), f
            else: #Solution requires a fourth root
                s2 = _mexpand(v[1]*R) + d
                if s2 <= 0:
                    return sqrt(nested[-1]), [0]*len(nested)
                FR, s = root(_mexpand(R), 4), sqrt(s2)
                return _mexpand(s/(sqrt(2)*FR) + v[0]*FR/(sqrt(2)*s)), f

def subsets(n):
    """
    Returns all possible subsets of the set (0, 1, ..., n-1) except the
    empty set, listed in reversed lexicographical order according to binary
    representation, so that the case of the fourth root is treated last.

    Examples
    ========

    >>> from sympy.simplify.sqrtdenest import subsets
    >>> subsets(3)
    [[1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]]

    """
    if n == 1:
        a = [[1]]
    elif n == 2:
        a = [[1, 0], [0, 1], [1, 1]]
    elif n == 3:
        a = [[1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]]
    else:
        b = subsets(n-1)
        a0 = [x+[0] for x in b]
        a1 = [x+[1] for x in b]
        a = a0 + [[0]*(n-1) + [1]] + a1
    return a
