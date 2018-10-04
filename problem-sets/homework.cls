\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{handout}[2009/11/30 v0.1 Jim Fowler's Homework class]

% Passes and class options to the underlying article class
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions

% Load LaTeX's article class
\LoadClass[12pt]{article}

\makeatletter
\newcommand{\@course}{Mathematics}
\newcommand{\course}[1]{\renewcommand{\@course}{#1}}
\makeatother

\date{\ifcase\month\or Winter\or Winter\or March\or Spring\or Spring\or Spring\or Summer\or Summer\or Autumn\or Autumn\or Autumn\or Autumn\fi\space\number\year}

\usepackage{graphicx}
\usepackage{geometry}
\geometry{margin=1.25in,left=1.6in,top=0.5in,bottom=0.8in}

\expandafter\def\expandafter\removemewbb\detokenize{set}{}
\edef\problemsetnumber{\expandafter\removemewbb\jobname}
\newcounter{problemset}
\setcounter{problemset}{\problemsetnumber}
\usepackage{fmtcount}% http://ctan.org/pkg/fmtcount

\usepackage[compact]{titlesec}
\makeatletter
\renewcommand{\maketitle}{%
  \begin{center}
    \textbf{Linear Algebra and Differential Equations: Problem Set \#\arabic{problemset}} \\
    \@course \quad {\ifcase\month\or Winter\or Winter\or March\or Spring\or Spring\or Spring\or Summer\or Autumn\or Autumn\or Autumn\or Autumn\or Autumn\fi\space\number\year}
  \end{center}\vspace{-3ex}
  }
\makeatother

\titleformat{\section}{\bfseries}{}{0pt}{}

\usepackage{amsmath}
\usepackage{amsthm}
\newtheorem{theorem}{Theorem}
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{proposition}[theorem]{Proposition}

\theoremstyle{definition}
\newtheorem{remark}[theorem]{Remark}
\newtheorem{example}[theorem]{Example}
\newtheorem{definition}[theorem]{Definition}

\usepackage{amssymb}
\newcommand{\R}{\mathbb{R}}
\newcommand{\Z}{\mathbb{Z}}
\newcommand{\N}{\mathbb{N}}

\makeatletter
\newcounter{problem}
\newenvironment{problem}{\makebox[0pt][r]{\refstepcounter{problem}\textbf{S\padzeroes[2]{\decimal{problemset}}P\padzeroes[2]{\decimal{problem}}.}\hspace{1em}}\edef\@currentlabel{S\ifnum\theproblemset<10 0\theproblemset \else \theproblemset \fi P\ifnum\theproblem<10 0\theproblem\else\theproblem\fi}\ignorespaces}{\vspace{1ex}}
\makeatother

\newenvironment{problem*}{\makebox[0pt][r]{\refstepcounter{problem}\textbf{$\ast$ S\padzeroes[2]{\decimal{problemset}}P\padzeroes[2]{\decimal{problem}}.}\hspace{1em}}\ignorespaces}{\vspace{1ex}}
\setlength{\parindent}{0in}
\setlength{\parskip}{1ex}

\newenvironment{inspiration}{\begin{center}\footnotesize\em}{\end{center}\vspace{-1ex}}
\newcommand{\byline}[1]{ \rm---#1} 

\usepackage{sansmath}
\usepackage{xcolor}
\newenvironment{solution}{\vspace{-1.75ex}\color{red!50!gray}\sffamily\sansmath}{\color{black}\rmfamily\vspace{1ex}}

\makeatletter
\font\dummyft@=dummy \relax
\def\suppress{%
  \begingroup\par
  \parskip\z@
  \offinterlineskip
  \baselineskip=\z@skip
  \lineskip=\z@skip
  \lineskiplimit=\maxdimen
  \dummyft@
  \count@\sixt@@n
  \loop\ifnum\count@ >\z@
    \advance\count@\m@ne
    \textfont\count@\dummyft@
    \scriptfont\count@\dummyft@
    \scriptscriptfont\count@\dummyft@
  \repeat
  \let\selectfont\relax
  \let\mathversion\@gobble
  \let\getanddefine@fonts\@gobbletwo
  \tracinglostchars\z@
  \frenchspacing
  \hbadness\@M}
\def\endsuppress{\par\endgroup}
\makeatother

\renewenvironment{solution}{\suppress}{\endsuppress}

\usepackage{nopageno}


%\geometry{margin=1cm}

% That's all, folks!
\endinput
